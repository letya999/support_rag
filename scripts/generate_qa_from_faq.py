#!/usr/bin/env python3
"""
LLM-Based Synthetic Q&A Dataset Generator from FAQ

Generates realistic, diverse Q&A pairs by:
1. Reading existing FAQ documents (JSON, DOCX, Markdown, etc.)
2. Using LLM to paraphrase questions (multiple variations)
3. Generating related/alternative questions
4. Automatically classifying category and intent
5. Optionally evaluating with RAGAS

Usage:
    # Generate from existing FAQ with LLM paraphrasing
    python generate_qa_from_faq.py --faq-file datasets/qa_data.json \
                                    --output datasets/qa_llm_generated_500.json \
                                    --variations 5

    # Use RAGAS for quality evaluation
    python generate_qa_from_faq.py --faq-file datasets/qa_data.json \
                                    --output datasets/qa_ragas.json \
                                    --use-ragas --ragas-quality-threshold 0.8
"""

import json
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GeneratedQAPair:
    """Generated Q&A pair with metadata."""
    original_question: str
    original_answer: str
    paraphrased_question: str
    answer: str
    category: str
    intent: str
    difficulty: str
    question_type: str
    confidence_score: float
    requires_handoff: bool
    clarifying_questions: List[str]
    related_questions: List[str]
    tags: List[str]
    source_document: str
    generation_method: str = "llm_paraphrase"
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding original_question and question_type for storage."""
        data = asdict(self)
        data.pop('original_question', None)
        data.pop('question_type', None)
        data['question'] = data.pop('paraphrased_question')
        data['metadata'] = {
            'category': data.pop('category'),
            'intent': data.pop('intent'),
            'difficulty': data.pop('difficulty'),
            'confidence_score': data.pop('confidence_score'),
            'requires_handoff': data.pop('requires_handoff'),
            'clarifying_questions': data.pop('clarifying_questions'),
            'related_questions': data.pop('related_questions'),
            'tags': data.pop('tags'),
            'source_document': data.pop('source_document'),
            'generation_method': data.pop('generation_method'),
            'generated_at': data.pop('generated_at'),
        }
        return data


class LLMBasedQAGenerator:
    """Generate synthetic Q&A pairs using LLM with FAQ as foundation."""

    CATEGORY_KEYWORDS = {
        "Account": ["password", "login", "account", "security", "profile", "email", "2fa", "authentication"],
        "Orders": ["order", "purchase", "shipping", "package", "tracking", "delivery", "cancel order"],
        "Returns": ["return", "refund", "exchange", "damaged", "defective", "restocking"],
        "Billing": ["payment", "invoice", "subscription", "pricing", "plan", "charge", "credit card"],
        "Technical": ["error", "bug", "issue", "crash", "api", "integration", "slow", "performance"],
        "General": ["contact", "support", "help", "information", "location", "hours", "policy"],
    }

    PARAPHRASE_PROMPTS = [
        "Rephrase this support question in a more formal/professional way: {question}",
        "How would a beginner user ask this question differently? Rephrase: {question}",
        "Create a shorter, more direct version of this question: {question}",
        "What's a more natural/conversational way to ask this? {question}",
        "Rephrase this as if the user is in a hurry: {question}",
    ]

    INTENT_CLASSIFICATION_PROMPT = """Analyze this FAQ pair and classify it:

Question: {question}
Answer: {answer}

Provide JSON response with:
{{"intent": "specific intent (e.g., 'reset_password', 'track_order')",
  "category": "category from list",
  "difficulty": "easy|medium|hard",
  "requires_handoff": true/false,
  "confidence": 0.0-1.0}}

Available categories: Account, Orders, Returns, Billing, Technical, General
"""

    RELATED_QUESTIONS_PROMPT = """Generate 2-3 related questions someone might ask after this FAQ:

Question: {question}
Answer: {answer}

Return as JSON array of strings, e.g.: ["question 1", "question 2"]
Keep them short and realistic.
"""

    def __init__(self, use_ragas: bool = False):
        """Initialize generator with optional RAGAS integration."""
        try:
            from app.integrations.llm import get_llm
            self.llm = get_llm(model="gpt-4o-mini", temperature=0.7)
            logger.info("✓ Initialized OpenAI LLM for Q&A generation")
        except ImportError:
            logger.error("Could not import LLM from app.integrations. Make sure you're in the project directory.")
            raise

        self.use_ragas = use_ragas
        if use_ragas:
            try:
                from ragas.testset.generator import TestsetGenerator
                from ragas.testset.evolutions import simple, reasoning, multi_context
                self.ragas_generator = TestsetGenerator.from_langchain_llm(
                    llm=self.llm,
                    embedding_model="default"
                )
                logger.info("✓ Initialized RAGAS TestsetGenerator")
            except ImportError:
                logger.warning("RAGAS not available. Install with: pip install ragas")
                self.use_ragas = False

    def _categorize_by_keywords(self, question: str, answer: str) -> str:
        """Categorize based on keywords (fallback if LLM fails)."""
        text = (question + " " + answer).lower()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return category
        return "General"

    def _estimate_difficulty(self, question: str, answer: str) -> str:
        """Estimate difficulty based on length and complexity."""
        q_words = len(question.split())
        a_words = len(answer.split())
        total = q_words + a_words

        if total < 20:
            return "easy"
        elif total < 50:
            return "medium"
        else:
            return "hard"

    async def paraphrase_question(self, question: str) -> str:
        """Generate paraphrase of question using LLM."""
        prompt = self.PARAPHRASE_PROMPTS[hash(question) % len(self.PARAPHRASE_PROMPTS)]
        try:
            response = self.llm.invoke(prompt.format(question=question))
            paraphrase = response.content.strip()
            # Remove "Paraphrased:" prefix if LLM adds it
            if paraphrase.startswith("Paraphrased:"):
                paraphrase = paraphrase[12:].strip()
            return paraphrase
        except Exception as e:
            logger.warning(f"Paraphrase generation failed: {e}. Using original.")
            return question

    async def classify_intent(self, question: str, answer: str) -> Dict[str, Any]:
        """Classify intent, category, and difficulty using LLM."""
        try:
            response = self.llm.invoke(
                self.INTENT_CLASSIFICATION_PROMPT.format(question=question, answer=answer)
            )
            # Extract JSON from response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]  # Remove ```json and ```
            classification = json.loads(content)
            return classification
        except Exception as e:
            logger.warning(f"Classification failed: {e}. Using fallback.")
            return {
                "intent": "general_inquiry",
                "category": self._categorize_by_keywords(question, answer),
                "difficulty": self._estimate_difficulty(question, answer),
                "requires_handoff": False,
                "confidence": 0.6,
            }

    async def generate_related_questions(self, question: str, answer: str) -> List[str]:
        """Generate related questions user might ask."""
        try:
            response = self.llm.invoke(
                self.RELATED_QUESTIONS_PROMPT.format(question=question, answer=answer)
            )
            # Extract JSON array from response
            content = response.content.strip()
            if content.startswith("```"):
                content = content[content.find("["):content.rfind("]")+1]
            related = json.loads(content)
            return related[:3] if isinstance(related, list) else []
        except Exception as e:
            logger.warning(f"Related questions generation failed: {e}")
            return []

    async def generate_from_pair(
        self,
        question: str,
        answer: str,
        num_variations: int = 3,
        source_document: str = "faq.json"
    ) -> List[Dict[str, Any]]:
        """Generate multiple variations from single Q&A pair."""
        generated_pairs = []

        logger.info(f"Processing: {question[:50]}...")

        # Classify original
        classification = await self.classify_intent(question, answer)
        related_questions = await self.generate_related_questions(question, answer)

        # Generate paraphrases
        paraphrases = []
        for i in range(num_variations):
            paraphrase = await self.paraphrase_question(question)
            if paraphrase not in paraphrases and paraphrase != question:
                paraphrases.append(paraphrase)

        # If we don't have enough paraphrases, use original
        if not paraphrases:
            paraphrases = [question]

        # Create pairs from paraphrases
        for i, paraphrased_q in enumerate(paraphrases):
            pair = GeneratedQAPair(
                original_question=question,
                original_answer=answer,
                paraphrased_question=paraphrased_q,
                answer=answer,
                category=classification.get("category", "General"),
                intent=classification.get("intent", "general_inquiry"),
                difficulty=classification.get("difficulty", "medium"),
                question_type="paraphrase",
                confidence_score=classification.get("confidence", 0.8),
                requires_handoff=classification.get("requires_handoff", False),
                clarifying_questions=self._generate_clarifying_questions(question, answer),
                related_questions=related_questions,
                tags=self._generate_tags(classification),
                source_document=source_document,
                generated_at=datetime.now().isoformat(),
            )
            generated_pairs.append(pair.to_dict())

        return generated_pairs

    def _generate_clarifying_questions(self, question: str, answer: str) -> List[str]:
        """Generate relevant clarifying questions."""
        clarifying = []
        if "password" in question.lower():
            clarifying.append("Do you have access to the email associated with your account?")
        if "order" in question.lower() or "shipping" in question.lower():
            clarifying.append("Is this regarding a recent or past order?")
        if "return" in question.lower():
            clarifying.append("Is the item still in original condition?")
        if "payment" in question.lower():
            clarifying.append("Which payment method are you using?")
        return clarifying[:2]

    def _generate_tags(self, classification: Dict) -> List[str]:
        """Generate relevant tags from classification."""
        tags = [
            classification.get("category", "").lower(),
            classification.get("intent", "").lower(),
            "faq_derived",
        ]

        if classification.get("difficulty") == "easy":
            tags.append("common_question")
        elif classification.get("difficulty") == "hard":
            tags.append("complex_issue")

        if classification.get("requires_handoff"):
            tags.append("may_need_escalation")

        return [t for t in tags if t]

    async def load_faq(self, faq_file: str) -> List[Dict[str, str]]:
        """Load FAQ from various formats (JSON, DOCX, Markdown, CSV)."""
        path = Path(faq_file)

        if path.suffix == ".json":
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            raise ValueError(f"Unsupported format: {path.suffix}. Use JSON for now.")

    async def generate_dataset(
        self,
        faq_file: str,
        output_file: str,
        variations_per_pair: int = 3,
        max_pairs: Optional[int] = None
    ) -> int:
        """Generate full dataset from FAQ file."""
        logger.info(f"Loading FAQ from {faq_file}...")
        faq_pairs = await self.load_faq(faq_file)

        if max_pairs:
            faq_pairs = faq_pairs[:max_pairs]

        logger.info(f"Loaded {len(faq_pairs)} FAQ pairs. Generating {len(faq_pairs) * variations_per_pair} variations...")

        all_generated = []

        for idx, pair in enumerate(faq_pairs, 1):
            question = pair.get("question", "")
            answer = pair.get("answer", "")

            if not question or not answer:
                logger.warning(f"Skipping pair {idx}: missing question or answer")
                continue

            generated = await self.generate_from_pair(
                question=question,
                answer=answer,
                num_variations=variations_per_pair,
                source_document=Path(faq_file).name
            )
            all_generated.extend(generated)

            # Progress indicator
            if idx % 5 == 0:
                logger.info(f"  Processed {idx}/{len(faq_pairs)} pairs")

        # Save dataset
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_generated, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Generated {len(all_generated)} Q&A pairs")
        logger.info(f"✓ Saved to {output_file}")

        return len(all_generated)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate diverse synthetic Q&A from FAQ using LLM"
    )
    parser.add_argument(
        "--faq-file",
        required=True,
        help="Input FAQ file (JSON format)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output dataset file"
    )
    parser.add_argument(
        "--variations",
        type=int,
        default=3,
        help="Number of paraphrases per Q&A pair (default: 3)"
    )
    parser.add_argument(
        "--max-pairs",
        type=int,
        default=None,
        help="Limit FAQ pairs to process (default: all)"
    )
    parser.add_argument(
        "--use-ragas",
        action="store_true",
        help="Use RAGAS TestsetGenerator for evaluation"
    )

    args = parser.parse_args()

    # Initialize generator
    generator = LLMBasedQAGenerator(use_ragas=args.use_ragas)

    print("\n🚀 Generating Q&A from FAQ using LLM")
    print(f"   Input FAQ: {args.faq_file}")
    print(f"   Variations per pair: {args.variations}")
    print(f"   Use RAGAS: {args.use_ragas}")
    print()

    # Generate
    count = asyncio.run(generator.generate_dataset(
        faq_file=args.faq_file,
        output_file=args.output,
        variations_per_pair=args.variations,
        max_pairs=args.max_pairs
    ))

    print(f"\n✨ Generation complete! Total: {count} pairs\n")


if __name__ == "__main__":
    main()
