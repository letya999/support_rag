from typing import List, Dict, Any
from .models import MergedContext, MergedContextSource

class ContextMerger:
    def __init__(self, max_tokens: int = 5000):
        self.max_tokens = max_tokens

    def merge_contexts(self, primary_doc: Dict[str, Any], related_docs: List[Dict[str, Any]]) -> MergedContext:
        """
        Merges the answers from multiple documents into a single context string.
        """
        combined_text = []
        qa_sources = []
        
        # 1. Add Primary Doc
        primary_answer = primary_doc.get("answer", "")
        primary_question = primary_doc.get("question", "")
        primary_metadata = primary_doc.get("metadata", {})
        
        combined_text.append(f"### Основной ответ\n{primary_answer}")
        qa_sources.append(MergedContextSource(
            question=primary_question,
            hop_level=0,
            score=1.0,
            category=primary_metadata.get("category", "N/A")
        ))
        
        # 2. Add Related Docs
        for i, doc in enumerate(related_docs):
            answer = doc.get("answer", "")
            question = doc.get("question", "")
            metadata = doc.get("metadata", {})
            category = metadata.get("category", "N/A")
            
            # Simple deduplication (by content or title)
            if any(answer == src.question for src in qa_sources): # This is a weak check, but placeholder
                continue
                
            combined_text.append(f"\n\n### Дополнительная информация ({category})\n{answer}")
            qa_sources.append(MergedContextSource(
                question=question,
                hop_level=1, # Simple hop level for now
                score=0.8, # Placeholder score
                category=category
            ))

        full_text = "\n".join(combined_text)
        
        # 3. Truncate if necessary (dummy token counting)
        # In a real scenario, use a tokenizer like tiktoken
        estimated_tokens = len(full_text) // 4 
        truncated = False
        if estimated_tokens > self.max_tokens:
            full_text = full_text[:self.max_tokens * 4]
            truncated = True
            
        return MergedContext(
            combined_text=full_text,
            qa_sources=qa_sources,
            total_tokens=estimated_tokens,
            truncated=truncated
        )
