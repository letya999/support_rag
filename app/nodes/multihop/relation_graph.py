from typing import List, Dict, Any, Optional
from collections import defaultdict

class RelationGraphBuilder:
    def __init__(self):
        self.category_index = defaultdict(list)
        self.intent_index = defaultdict(list)
        self.doc_map = {}
        self.graph = {}

    async def load_from_db(self):
        """
        Loads all documents from Postgres and builds the graph.
        """
        from app.storage.connection import get_db_connection
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT id, content, metadata FROM documents")
                rows = await cur.fetchall()
                documents = []
                for row in rows:
                    doc = {
                        "id": row[0],
                        "content": row[1],
                        "metadata": row[2]
                    }
                    documents.append(doc)
                self.build_relation_graph(documents)

    def build_relation_graph(self, documents: List[Dict[str, Any]]):
        """
        Builds indices for categorical and intentional relations.
        """
        # Clear existing indices
        self.category_index = defaultdict(list)
        self.intent_index = defaultdict(list)
        self.doc_map = {}
        self.graph = {}
        
        self.doc_map = {str(doc["id"]): doc for doc in documents}
        
        for doc_id, doc in self.doc_map.items():
            metadata = doc.get("metadata", {})
            category = metadata.get("category")
            intent = metadata.get("intent")
            
            if category:
                self.category_index[category].append(doc_id)
            if intent:
                self.intent_index[intent].append(doc_id)

        # Build connections
        for doc_id, doc in self.doc_map.items():
            metadata = doc.get("metadata", {})
            category = metadata.get("category")
            intent = metadata.get("intent")
            
            same_category = [d for d in self.category_index.get(category, []) if d != doc_id]
            same_intent = [d for d in self.intent_index.get(intent, []) if d != doc_id]
            
            # Extract clarifying questions for future link building
            clarifying_questions = metadata.get("clarifying_questions", [])
            
            self.graph[doc_id] = {
                "same_category": same_category,
                "same_intent": same_intent,
                "clarifying_topics": [] 
            }

    def find_related_docs(self, doc_id: str) -> Dict[str, List[str]]:
        return self.graph.get(str(doc_id), {
            "same_category": [],
            "same_intent": [],
            "clarifying_topics": []
        })

    def get_doc(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self.doc_map.get(str(doc_id))
