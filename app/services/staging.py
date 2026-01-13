import json
import uuid
import time
from typing import List, Optional, Dict, Any
from redis import asyncio as aioredis
from app.settings import settings
from app.services.ingestion.ingestion_service import DocumentIngestionService
from app.services.document_loaders import ProcessedQAPair
from app.logging_config import logger

class StagingService:
    """Service for managing staging drafts in Redis before they are committed to permanent storage."""
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
        """
        Create a new staging draft from a list of Q&A pairs.

        Args:
            filename: Name of the source file
            pairs: List of Q&A pair dicts

        Returns:
            Dict containing the created draft data
        """
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
        """
        Retrieve a draft by its ID.

        Args:
            draft_id: Unique draft identifier

        Returns:
            Dict containing draft data or None
        """
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
        """
        Commit a staging draft to permanent storage (Postgres and Qdrant).
        Deletes the draft from staging on success.

        Args:
            draft_id: Unique draft identifier

        Returns:
            Dict containing ingestion results
        """
        logger.info("Committing staging draft", extra={"draft_id": draft_id})
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

    async def list_drafts(self, draft_ids: Optional[List[str]] = None, search_term: Optional[str] = None) -> List[Dict[str, Any]]:
        redis = await self._get_redis()
        try:
            # This uses SCAN which is safe but might be slow if millions of keys.
            # Ideally we'd have a set of active drafts, but given this is staging, it's likely small.
            cursor = 0
            keys = []
            while True:
                cursor, new_keys = await redis.scan(cursor, match=f"{self.PREFIX}*", count=100)
                keys.extend(new_keys)
                if cursor == 0:
                    break
            
            if not keys:
                return []

            # Determine which keys to fetch
            # If draft_ids provided, filter keys first (optimization)
            keys_to_fetch = []
            if draft_ids:
                draft_keys = set(f"{self.PREFIX}{did}" for did in draft_ids)
                keys_to_fetch = [k for k in keys if k in draft_keys]
            else:
                keys_to_fetch = keys

            if not keys_to_fetch:
                return []

            # MGET for all filtered keys
            drafts_json = await redis.mget(keys_to_fetch)
            
            results = []
            for d_json in drafts_json:
                if d_json:
                    try:
                        d = json.loads(d_json)
                        # Text search (LIKE) on filename
                        if search_term:
                            if search_term.lower() not in d.get("filename", "").lower():
                                continue
                        results.append(d)
                    except:
                        continue
            
            return results
        finally:
            await redis.close()

    async def clear_all_drafts(self) -> int:
        """
        Deletes all staging drafts and file mappings.
        Returns the number of keys deleted.
        """
        redis = await self._get_redis()
        try:
            # Find all draft keys
            cursor = 0
            keys_to_delete = []
            while True:
                cursor, new_keys = await redis.scan(cursor, match=f"{self.PREFIX}*", count=100)
                keys_to_delete.extend(new_keys)
                if cursor == 0:
                    break
            
            # Find all file mapping keys
            cursor = 0
            while True:
                cursor, new_keys = await redis.scan(cursor, match=f"{self.FILE_PREFIX}*", count=100)
                keys_to_delete.extend(new_keys)
                if cursor == 0:
                    break
            
            if not keys_to_delete:
                return 0
                
            # Delete in batches of 100 to be safe
            deleted_count = 0
            batch_size = 100
            for i in range(0, len(keys_to_delete), batch_size):
                batch = keys_to_delete[i:i + batch_size]
                if batch:
                    deleted_count += await redis.delete(*batch)
                    
            return deleted_count
        finally:
            await redis.close()

staging_service = StagingService()
