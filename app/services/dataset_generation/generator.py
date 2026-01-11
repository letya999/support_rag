import json
import logging
from typing import List, Optional, Dict, Any
import random

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.integrations.llm import get_llm
from app.dataset.schema import EvalItem

logger = logging.getLogger(__name__)

class DatasetGenerator:
    """Service for generating synthetic datasets from various sources."""

    def __init__(self):
        # Ensure we use a capable model for generation (e.g., GPT-4o or similar high-capacity model)
        # Using streaming=False to get full response for parsing
        self.llm = get_llm(streaming=False) 

    async def generate_simple_dataset(self, description: Optional[str] = None, count: int = 5, is_random: bool = False) -> List[Dict[str, Any]]:
        """
        Generate simple Q&A pairs for basic population or fine-tuning.
        Output is a list of simple dicts: {"question": "...", "answer": "..."}
        """
        if is_random:
            topic = "a fictional random product or service"
            description_text = "Generate details for a random innovative product."
        else:
            topic = "the described product/service"
            description_text = description if description else "a generic service"

        logger.info(f"Generating {count} simple pairs for {topic}")
        
        system_template = """You are an expert data generator.
Your task is to generate {count} question-answer pairs about {topic}.
The output MUST be a valid JSON array of objects.
Each object must have:
- "question": A user query.
- "answer": A helpful response.

Context/Description:
{description_text}

Rules:
- Keep answers concise.
- Cover different aspects (features, pricing, support, etc.).
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", "Generate the pairs now.")
        ])

        chain = prompt | self.llm | JsonOutputParser()

        try:
            results = await chain.ainvoke({
                "count": count,
                "topic": topic,
                "description_text": description_text
            })
            
            # Normalize output
            pairs = []
            for r in results:
                if "question" in r and "answer" in r:
                    pairs.append({
                        "question": r["question"],
                        "answer": r["answer"]
                    })
            return pairs

        except Exception as e:
            logger.error(f"Error generating simple dataset: {e}")
            raise

    async def generate_ground_truth_from_data(self, input_data: List[Dict[str, Any]], adversarial_level: float) -> List[EvalItem]:
        """
        Generate a Ground Truth dataset (EvalItems) from existing Q&A data.
        
        Args:
            input_data: List of dicts with 'question', 'answer', and optional 'metadata'.
            adversarial_level: Float from 0.0 (close paraphrase) to 1.0 (hard adversarial).
        """
        logger.info(f"Generating GT dataset from {len(input_data)} items. Adversarial Level: {adversarial_level}")
        
        generated_items = []
        
        # We can process in batches to save time, but for quality, item-by-item or small batches is better.
        # Let's do small batches of 5 to keep context clear but speed up.
        batch_size = 5
        
        for i in range(0, len(input_data), batch_size):
            batch = input_data[i:i+batch_size]
            items = await self._process_gt_batch(batch, adversarial_level)
            generated_items.extend(items)
            
        return generated_items

    async def _process_gt_batch(self, batch: List[Dict[str, Any]], adversarial_level: float) -> List[EvalItem]:
        
        # Prepare batch prompt
        system_template = """You are an expert dataset creator for RAG evaluation.
Your task is to take a list of input Q&A pairs and transform them into "Ground Truth" Evaluation Items.

Adversarial Level: {adversarial_level} (0.0 = minimal changes, 1.0 = highly complex/adversarial).

For EACH input item, generate an object with:
- "question": A rewritten user query based on the Input Question/Answer.
    - If level is close to 0: Paraphrase slightly.
    - If level is close to 1: Make it vague, complex, use slang, typos, or indirect reasoning that requires the answer.
- "expected_answer": The ideal ground truth answer (usually the Input Answer, maybe refined).
- "expected_chunks": A list containing the Input Answer (treated as the source of truth).
- "expected_intent": Extracted or inferred intent.
- "expected_category": Extracted or inferred category.

Input Batch:
{batch_json}

Output MUST be a valid JSON array of objects.
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
        ])

        chain = prompt | self.llm | JsonOutputParser()
        
        try:
            results = await chain.ainvoke({
                "adversarial_level": adversarial_level,
                "batch_json": json.dumps(batch, ensure_ascii=False)
            })
            
            items = []
            for r in results:
                # Basic validation
                items.append(EvalItem(
                    question=r.get("question", ""),
                    expected_answer=r.get("expected_answer", ""),
                    expected_chunks=r.get("expected_chunks", []),
                    expected_intent=r.get("expected_intent"),
                    expected_category=r.get("expected_category"),
                    expected_action=r.get("expected_action")
                ))
            return items
            
        except Exception as e:
            logger.error(f"Error processing GT batch: {e}")
            # Fallback: just convert input 1:1 if LLM fails
            fallback = []
            for b in batch:
                fallback.append(EvalItem(
                    question=b.get("question", ""),
                    expected_answer=b.get("answer", ""),
                    expected_chunks=[b.get("answer", "")],
                    expected_intent=b.get("metadata", {}).get("intent"),
                    expected_category=b.get("metadata", {}).get("category")
                ))
            return fallback

    # Keep previous methods for compatibility if needed, but the new ones cover the requirements.
    async def generate_from_text(self, text: str, count: int = 5, instructions: Optional[str] = None) -> List[EvalItem]:
        """Legacy/compatibility wrapper."""
        # Adapted logic for text source... reusing simple generation structure but formatted as EvalItem
        # (Implementation details omitted for brevity as user focused on the two new flows)
        # But to be safe, I'll keep the original method logic if I overwrote the file.
        # Actually I will overwrite the file, so I need to make sure I don't break "generate_from_text" if I want to keep it.
        # The user's request specific about "Simple" and "Ground Truth".
        # I'll re-implement generate_from_text to use the new simple logic but map to EvalItems.
        pass
    
    # Re-adding original methods for full utility
    async def generate_from_text(self, text: str, count: int = 5, instructions: Optional[str] = None) -> List[EvalItem]:
         logger.info(f"Generating {count} pairs from text sample (len={len(text)})")
         system_template = """Analyze the text and generate {count} Q&A pairs (EvalItems).
         Instructions: {instructions}
         Output JSON array."""
         
         prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", "Text:\n{text}")
        ])
         chain = prompt | self.llm | JsonOutputParser()
         results = await chain.ainvoke({"count": count, "instructions": instructions or "Focus on accuracy.", "text": text})
         return [EvalItem(question=r.get("question"), expected_answer=r.get("expected_answer"), expected_chunks=r.get("expected_chunks", [])) for r in results if "question" in r]

    async def generate_from_prompt(self, prompt_text: str, count: int = 5) -> List[EvalItem]:
         # Similar to simple but returns EvalItems
         pairs = await self.generate_simple_dataset(description=prompt_text, count=count)
         return [EvalItem(question=p["question"], expected_answer=p["answer"], expected_chunks=[]) for p in pairs]
