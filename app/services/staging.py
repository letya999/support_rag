import json
import uuid
import time
from typing import List, Optional, Dict, Any
from redis import asyncio as aioredis
from app.settings import settings
from app.services.ingestion.ingestion_service import DocumentIngestionService
from app.services.document_loaders import ProcessedQAPair
import logging

logger = logging.getLogger(__name__)

class StagingService:
    PREFIX = "staging:draft:"
    FILE_PREFIX = "staging:file:"
    EXPIRY = 86400 * 7 # 7 days
    
    def __init__(self):
        self.redis_url = settings.REDIS_URL
    
    async def _get_redis(self):
        return await aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)

    def _generate_id(self):
        return str(uuid.uuid4())

    async def create_draft(self, filename: str, pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        draft_id = self._generate_id()
        file_id = self._generate_id()
        
        # Structure locally
        chunks = []
        for p in pairs:
            chunk_id = self._generate_id()
            chunks.append({
                "chunk_id": chunk_id,
                "question": p.get("question"),
                "answer": p.get("answer"),
                "metadata": p.get("metadata", {})
            })
            
        draft_data = {
            "draft_id": draft_id,
            "file_id": file_id,
            "filename": filename,
            "created_at": time.time(),
            "status": "draft",
            "chunks": chunks
        }
        
        redis = await self._get_redis()
        try:
            key = f"{self.PREFIX}{draft_id}"
            file_key = f"{self.FILE_PREFIX}{file_id}"
            
            async with redis.pipeline() as pipe:
                await pipe.set(key, json.dumps(draft_data), ex=self.EXPIRY)
                await pipe.set(file_key, draft_id, ex=self.EXPIRY)
                await pipe.execute()
                
            return draft_data
        finally:
            await redis.close()

    async def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        redis = await self._get_redis()
        try:
            key = f"{self.PREFIX}{draft_id}"
            data = await redis.get(key)
            if data:
                return json.loads(data)
            return None
        finally:
            await redis.close()
            
    async def get_draft_by_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        redis = await self._get_redis()
        try:
            file_key = f"{self.FILE_PREFIX}{file_id}"
            draft_id = await redis.get(file_key)
            if draft_id:
                return await self.get_draft(draft_id)
            return None
        finally:
            await redis.close()

    async def update_chunk(self, draft_id: str, chunk_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        redis = await self._get_redis()
        try:
            key = f"{self.PREFIX}{draft_id}"
            data = await redis.get(key)
            if not data:
                return None
            
            draft = json.loads(data)
            found = False
            for chunk in draft["chunks"]:
                if chunk["chunk_id"] == chunk_id:
                    chunk.update(updates)
                    found = True
                    break
            
            if found:
                await redis.set(key, json.dumps(draft), ex=self.EXPIRY)
                return draft
            return None
        finally:
            await redis.close()

    async def update_chunk_metadata_batch(self, draft_id: str, updates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Batch update metadata for multiple chunks.
        updates: List of dicts with 'chunk_id' and 'metadata' keys.
        """
        redis = await self._get_redis()
        try:
            key = f"{self.PREFIX}{draft_id}"
            data = await redis.get(key)
            if not data:
                return None
            
            draft = json.loads(data)
            
            # Create a map for faster lookup
            update_map = {u['chunk_id']: u['metadata'] for u in updates}
            
            updates_count = 0
            for chunk in draft["chunks"]:
                if chunk["chunk_id"] in update_map:
                    # Merge metadata
                    current_meta = chunk.get("metadata", {})
                    current_meta.update(update_map[chunk["chunk_id"]])
                    chunk["metadata"] = current_meta
                    updates_count += 1
            
            if updates_count > 0:
                await redis.set(key, json.dumps(draft), ex=self.EXPIRY)
                return draft
            return draft # Return draft even if no updates happened, but it exists
        finally:
            await redis.close()

    async def add_chunks(self, draft_id: str, new_chunks_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        redis = await self._get_redis()
        try:
            key = f"{self.PREFIX}{draft_id}"
            data = await redis.get(key)
            if not data:
                return None
            
            draft = json.loads(data)
            for ch in new_chunks_data:
                chunk_id = self._generate_id()
                draft["chunks"].append({
                    "chunk_id": chunk_id,
                    "question": ch.get("question"),
                    "answer": ch.get("answer"),
                    "metadata": ch.get("metadata", {})
                })
            
            await redis.set(key, json.dumps(draft), ex=self.EXPIRY)
            return draft
        finally:
            await redis.close()

    async def delete_chunk(self, draft_id: str, chunk_id: str) -> bool:
        redis = await self._get_redis()
        try:
            key = f"{self.PREFIX}{draft_id}"
            data = await redis.get(key)
            if not data:
                return False
            
            draft = json.loads(data)
            original_len = len(draft["chunks"])
            draft["chunks"] = [c for c in draft["chunks"] if c["chunk_id"] != chunk_id]
            
            if len(draft["chunks"]) < original_len:
                await redis.set(key, json.dumps(draft), ex=self.EXPIRY)
                return True
            return False
        finally:
            await redis.close()
            
    async def delete_draft(self, draft_id: str) -> bool:
        redis = await self._get_redis()
        try:
            key = f"{self.PREFIX}{draft_id}"
            
            # Need to find file_id to delete the mapping
            data = await redis.get(key)
            file_id = None
            if data:
                try:
                    draft = json.loads(data)
                    file_id = draft.get("file_id")
                except:
                    pass
            
            async with redis.pipeline() as pipe:
                await pipe.delete(key)
                if file_id:
                    file_key = f"{self.FILE_PREFIX}{file_id}"
                    await pipe.delete(file_key)
                res = await pipe.execute()
                
            return res[0] > 0
        finally:
            await redis.close()
            
    async def commit_draft(self, draft_id: str) -> Dict[str, Any]:
        draft = await self.get_draft(draft_id)
        if not draft:
            raise ValueError("Draft not found")
            
        processed_pairs = []
        for chunk in draft["chunks"]:
            if not chunk.get("question") or not chunk.get("answer"):
                continue
                
            processed_pairs.append(
                ProcessedQAPair(
                    question=chunk["question"],
                    answer=chunk["answer"],
                    metadata=chunk.get("metadata", {})
                )
            )
            
        if not processed_pairs:
             return {"status": "empty", "ingested_count": 0}

        # Call Ingestion Service
        result = await DocumentIngestionService.ingest_pairs(processed_pairs)
        
        # Clean up draft after successful commit
        if result.get("status") == "success":
            await self.delete_draft(draft_id)
            
        return result

staging_service = StagingService()
