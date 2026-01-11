import json
import logging
import asyncio
from typing import List, Dict, Any
import numpy as np
from pydantic import BaseModel

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.integrations.llm import get_llm
from app.services.classification.semantic_service import SemanticClassificationService

# Try to import sklearn, fallback gracefully if missing (though required for this logic)
try:
    from sklearn.cluster import KMeans
    from sklearn.metrics import pairwise_distances_argmin_min
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)

class DiscoveryResult(BaseModel):
    chunk_id: str
    intent: str
    category: str
    confidence: float = 0.85

class DiscoveryService:
    """
    Service for Unsupervised Intent Discovery via Clustering (Embed -> Cluster -> LLM Label).
    Efficiently handles large datasets by clustering first and only sending samples to LLM.
    """
    
    def __init__(self):
        self.llm = get_llm(streaming=False)
        self.semantic_service = SemanticClassificationService()

    async def discover_intents(self, chunks: List[Dict[str, Any]]) -> List[DiscoveryResult]:
        """
        Hierarchical Clustering & Labeling:
        1. Embed all questions.
        2. Cluster into N Categories (4-20 depending on size).
        3. For each Category Cluster, Cluster into M Intents (2-10).
        4. Collect samples for all groups.
        5. Ask LLM to name Categories and Intents.
        6. Assign results.
        """
        if not SKLEARN_AVAILABLE:
            logger.error("scikit-learn not found. Cannot perform clustering.")
            return []

        valid_chunks = [c for c in chunks if c.get("question")]
        if not valid_chunks:
            return []
            
        texts = [c["question"] for c in valid_chunks]
        ids = [c["chunk_id"] for c in valid_chunks]
        n_docs = len(texts)
        
        # 1. Embed
        logger.info(f"Embedding {n_docs} chunks for hierarchical discovery...")
        embeddings = await self.semantic_service.encode_batch(texts)
        if len(embeddings) == 0:
            return []

        # 2. Determine Category Count (N)
        # Rule: 4 to 20 categories.
        # Logarithmic scale or simple interpolation?
        # < 20 docs -> 4 categories? No, max 1 item per category.
        # Let's say: 
        #   If n < 10: N = max(2, n_docs // 2)
        #   If 10 <= n <= 1000: Interpolate 4 to 20
        #   If n > 1000: 20
        
        if n_docs < 10:
             n_categories = max(2, min(n_docs, 4))
        else:
             # simple linear interp between (10, 4) and (1000, 20)
             # slope = (20 - 4) / (1000 - 10) ~ 0.016
             n_categories = int(4 + (n_docs - 10) * ((20 - 4) / (990)))
             n_categories = min(20, max(4, n_categories))
             
        logger.info(f"Docs: {n_docs} -> Categories: {n_categories}")
        
        loop = asyncio.get_running_loop()
        
        # --- Level 1: Categories ---
        def run_kmeans(data, k):
            if len(data) < k:
                k = max(1, len(data))
            km = KMeans(n_clusters=k, random_state=42, n_init=5)
            km.fit(data)
            return km, k

        cat_kmeans, real_n_cats = await loop.run_in_executor(None, run_kmeans, embeddings, n_categories)
        cat_labels = cat_kmeans.labels_
        
        prompts_structure = [] # To send to LLM
        
        # Determine Intents for each Category
        category_clusters = {} # cat_id -> { "indices": [], "sub_clusters": ... }
        
        # Group indices by category
        for idx, label in enumerate(cat_labels):
            if label not in category_clusters:
                category_clusters[label] = []
            category_clusters[label].append(idx)
            
        # Process each category
        for cat_id, indices in category_clusters.items():
            cat_indices = np.array(indices)
            cat_embeddings = np.array([embeddings[i] for i in indices])
            n_in_cat = len(cat_indices)
            
            # Determine Intent Count (M)
            # Rule: 2 to 10 intents within category
            if n_in_cat < 4:
                n_intents = 1 # Too small to split
            else:
                # scale
                target = int(2 + (n_in_cat / 50) * 8) # rough heuristic
                n_intents = min(10, max(2, target))
            
            if n_intents >= n_in_cat:
                n_intents = 1
                
            # --- Level 2: Intents ---
            intent_kmeans, real_n_intents = await loop.run_in_executor(None, run_kmeans, cat_embeddings, n_intents)
            intent_labels = intent_kmeans.labels_
            
            # Prepare samples for this category
            cat_structure = {
                "category_id": int(cat_id),
                "intents": []
            }
            
            # For each intent sub-cluster, get 3 samples
            for int_id in range(real_n_intents):
                # indices relative to cat_embeddings
                sub_indices = np.where(intent_labels == int_id)[0]
                if len(sub_indices) == 0: continue
                
                # Get closest to intent center
                sub_emb = cat_embeddings[sub_indices]
                center = intent_kmeans.cluster_centers_[int_id].reshape(1, -1)
                
                from sklearn.metrics.pairwise import euclidean_distances
                dists = euclidean_distances(sub_emb, center).flatten()
                
                # Top 2 closest (as requested by user)
                top_k_local_idx = dists.argsort()[:2]
                
                samples = []
                for k in top_k_local_idx:
                    # Map back to global Index
                    original_global_idx = cat_indices[sub_indices[k]]
                    samples.append(texts[original_global_idx])
                    
                cat_structure["intents"].append({
                    "intent_local_id": int(int_id),
                    "samples": samples
                })
                
            prompts_structure.append(cat_structure)
            
        # 4. LLM Labeling
        logger.info(f"Asking LLM to name {len(prompts_structure)} Categories and their Intents...")
        definitions = await self._label_hierarchical(prompts_structure)
        
        # 5. Assign and Return
        return await self._assign_and_return(ids, cat_labels, category_clusters, prompts_structure, definitions, embeddings)

    async def _assign_and_return(self, ids, cat_labels, category_clusters, prompts_structure, definitions, embeddings):
        """
        Assign final labels to all chunks by re-mapping the cluster structure.
        """
        output = []
        
        # Iterate over the structure we built to match items back to intents
        for cat_data in prompts_structure:
            cat_id = cat_data["category_id"]
            global_indices = category_clusters[cat_id]
            
            # Get definition for this category from LLM
            cat_def = definitions.get(cat_id, {})
            cat_name = cat_def.get("category_name", f"Category {cat_id}")
            intent_defs = cat_def.get("intents", {})
            
            # We need to assign each global_index to a specific intent_local_id.
            # Since we didn't save the per-item intent labels in the main loop (to avoid excessive memory/state passing),
            # we re-cluster this specific subset using the EXACT same params (seed=42).
            # This is deterministic and safe for this context.
            
            sub_emb = np.array([embeddings[i] for i in global_indices])
            n_intents = len(cat_data["intents"])
            
            # If no intents defined (shouldn't happen with our logic), everything is intent 0
            if n_intents == 0:
                 labels = [0] * len(global_indices)
            elif n_intents == 1:
                 labels = [0] * len(global_indices)
            else:
                # Re-run K-Means for this subset
                km = KMeans(n_clusters=n_intents, random_state=42, n_init=5)
                km.fit(sub_emb)
                labels = km.labels_
                
            for i, local_label in enumerate(labels):
                chunk_id = ids[global_indices[i]]
                
                # Get intent name mapping
                intent_name = intent_defs.get(local_label, f"intent_{local_label}")
                
                output.append(DiscoveryResult(
                    chunk_id=chunk_id,
                    intent=intent_name,
                    category=cat_name,
                    confidence=0.9
                ))
                
        return output

    async def _label_hierarchical(self, structure: List[Dict]) -> Dict:
        """
        Ask LLM to name Categories and their Intents.
        """
        # Simplify structure for LLM (remove IDs where possible or keep minimal)
        # We need: Category ID -> Samples -> Intents -> Samples
        
        system_template = """You are a taxonomy expert.
Analyze the provided Hierarchical Clusters of support tickets.

Input Format:
[
  {{
    "category_id": 0,
    "intents": [
      {{ "intent_local_id": 0, "samples": ["...", "..."] }},
       ...
    ]
  }},
  ...
]

Task:
1. Identify the Language (Russian or English). Output names in that language.
2. For each `category_id`:
   - Assign a "category_name" (Title Case, e.g., "Technical Issues", "Account Access").
   - ONE category MUST be related to "Technical Issues" / "Failures" if the data supports it.
3. For each `intent_local_id` inside it:
   - Assign an "intent" (snake_case, e.g., "connection_error", "restore_password").

Output JSON:
{{
  "0": {{
    "category_name": "...", 
    "intents": {{
       "0": "intent_name",
       "1": "intent_name"
    }}
  }},
  ...
}}
"""
        user_input = json.dumps(structure, ensure_ascii=False, indent=2)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", "Data:\n{input_data}")
        ])
        
        chain = prompt | self.llm | JsonOutputParser()
        try:
             # Normalize keys to int
            raw = await chain.ainvoke({"input_data": user_input})
            logger.info(f"LLM Labeling Raw Output: {json.dumps(raw, indent=2, ensure_ascii=False)}")
            
            normalized = {}
            for k, v in raw.items():
                try:
                    k_int = int(k)
                    intents_raw = v.get("intents", {})
                    intents_norm = {}
                    for ik, iv in intents_raw.items():
                         try: 
                             # intent keys might be strings "0", "1"
                             intents_norm[int(ik)] = iv
                         except: 
                             logger.warning(f"Skipping malformed intent key: {ik}")
                             continue
                    
                    normalized[k_int] = {
                        "category_name": v.get("category_name", f"Category {k}"),
                        "intents": intents_norm
                    }
                except ValueError:
                    logger.warning(f"Skipping malformed category key: {k}")
                    continue
            
            logger.info(f"Normalized definitions: {normalized.keys()}")
            return normalized
        except Exception as e:
            logger.error(f"Error labeling hierarchical: {e}", exc_info=True)
            return {}
