import time
import asyncio
from typing import List, Dict, Any, Optional
from .models import HopResolverOutput, HopDetail
from .relation_graph import RelationGraphBuilder
from .context_merger import ContextMerger
from app.storage.connection import get_db_connection

class HopResolver:
    def __init__(self, relation_builder: RelationGraphBuilder, context_merger: ContextMerger):
        self.relation_builder = relation_builder
        self.context_merger = context_merger

    async def resolve(self, question: str, initial_docs: List[str], initial_scores: List[float], initial_metadata: List[Dict[str, Any]], num_hops: int) -> HopResolverOutput:
        start_time = time.time()
        
        if not initial_docs:
            return HopResolverOutput(retrieval_time=time.time() - start_time)

        # Hop 0: Already performed by retrieval node
        primary_doc_content = initial_docs[0]
        primary_metadata = initial_metadata[0] if initial_metadata else {}
        
        # We need an ID to find relations. Let's assume metadata has an 'id' or we use some unique field.
        # Looking at storage.py, the ID from Qdrant/Postgres is used.
        primary_id = primary_metadata.get("id")
        
        hop_chain = [{
            "hop": 0,
            "query": question,
            "doc_ids": [str(primary_id)] if primary_id else [],
            "status": "completed"
        }]
        
        related_doc_ids = set()
        performed_hops = 1 # Hop 0 is done
        
        # If score is low or complexity is high, perform more hops
        if num_hops > 1:
            # Build graph if not built (ideally should be pre-built)
            # For now, let's assume it's pre-populated or we find relations on the fly
            
            # Find relations for the primary doc
            # If primary_id is missing, we can't find relations in the graph
            if primary_id:
                relations = self.relation_builder.find_related_docs(str(primary_id))
                
                # Combine related IDs
                candidates = set(relations.get("same_category", [])) | set(relations.get("same_intent", []))
                
                # Fetch content for these candidates if they are not the primary one
                if candidates:
                    for cid in candidates:
                        if cid != str(primary_id):
                            related_doc_ids.add(cid)
                    
                    hop_chain.append({
                        "hop": 1,
                        "type": "relation_graph",
                        "found_count": len(candidates),
                        "status": "completed"
                    })
                    performed_hops += 1

        # Fetch actual contents for related docs
        related_docs_data = []
        if related_doc_ids:
            async with get_db_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT content, metadata FROM documents WHERE id = ANY(%s)",
                        (list(related_doc_ids),)
                    )
                    rows = await cur.fetchall()
                    for row in rows:
                        related_docs_data.append({
                            "question": row[1].get("question", ""), # Assuming question is in metadata
                            "answer": row[0],
                            "metadata": row[1]
                        })

        # Merge contexts
        primary_doc_data = {
            "question": primary_metadata.get("question", question),
            "answer": primary_doc_content,
            "metadata": primary_metadata
        }
        
        merged = self.context_merger.merge_contexts(primary_doc_data, related_docs_data)

        return HopResolverOutput(
            primary_doc=primary_doc_content,
            related_docs=[d["answer"] for d in related_docs_data],
            hop_chain=hop_chain,
            merged_context=merged.combined_text,
            total_hops_performed=performed_hops,
            retrieval_time=time.time() - start_time,
            confidence=initial_scores[0] if initial_scores else 0.0
        )
