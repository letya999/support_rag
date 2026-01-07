#!/usr/bin/env python3
"""
RAGAS-Based Synthetic Q&A Dataset Generator

Uses RAGAS (Retrieval-Augmented Generation Assessment) TestsetGenerator
to create high-quality, diverse Q&A pairs from documents.

This is the professional-grade approach used in production RAG systems.

Installation:
    pip install ragas langchain langchain-openai

Usage:
    # Generate from documents with RAGAS
    python generate_qa_ragas.py --documents datasets/qa_data.json \
                                --output datasets/qa_ragas_generated.json \
                                --num-pairs 100 \
                                --evolutions simple reasoning multi_context

    # Use only FAQ-derived sources
    python generate_qa_ragas.py --documents datasets/qa_data.json \
                                --output datasets/qa_ragas_qa_grounded.json \
                                --num-pairs 500 \
                                --test-size 0.5
"""

import json
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGASQAGenerator:
    """Generate synthetic Q&A pairs using RAGAS framework."""

    def __init__(self, seed: int = 42):
        """Initialize RAGAS generator."""
        try:
            from ragas.testset.generator import TestsetGenerator
            from ragas.testset.evolutions import simple, reasoning, multi_context
            from langchain_community.document_loaders import TextLoader
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            # Initialize LLM
            try:
                from app.integrations.llm import get_llm
                llm = get_llm(model="gpt-4o-mini")
            except ImportError:
                from langchain_openai import ChatOpenAI
                import os
                llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            # Initialize embeddings
            try:
                from app.storage.embeddings import get_embeddings
                embeddings = get_embeddings()
            except ImportError:
                from langchain_openai import OpenAIEmbeddings
                embeddings = OpenAIEmbeddings()

            self.generator = TestsetGenerator.from_langchain_llm(
                llm=llm,
                embedding_model=embeddings
            )
            self.evolutions = {
                "simple": simple,
                "reasoning": reasoning,
                "multi_context": multi_context,
            }
            self.llm = llm
            self.embeddings = embeddings

            logger.info("✓ Initialized RAGAS TestsetGenerator")

        except ImportError as e:
            logger.error(f"RAGAS not installed: {e}")
            logger.info("Install with: pip install ragas")
            raise

    def load_documents_from_qa(self, qa_file: str) -> List[Any]:
        """Load documents from Q&A JSON file."""
        from langchain_core.documents import Document

        with open(qa_file, 'r', encoding='utf-8') as f:
            qa_pairs = json.load(f)

        documents = []
        for idx, pair in enumerate(qa_pairs):
            # Create document from answer (context)
            doc = Document(
                page_content=pair.get("answer", ""),
                metadata={
                    "original_question": pair.get("question", ""),
                    "doc_id": f"qa_{idx}",
                    "source": Path(qa_file).name,
                }
            )
            documents.append(doc)

        logger.info(f"Loaded {len(documents)} documents from {qa_file}")
        return documents

    def generate_testset(
        self,
        documents: List[Any],
        num_pairs: int = 100,
        test_size: float = 0.5,
        evolutions: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generate testset using RAGAS."""
        if evolutions is None:
            evolutions = ["simple", "reasoning"]

        # Validate evolutions
        evolutions = [e for e in evolutions if e in self.evolutions]
        if not evolutions:
            evolutions = ["simple"]

        logger.info(f"Generating {num_pairs} pairs with evolutions: {evolutions}")
        logger.info("This may take a while as it uses LLM for generation...")

        # Generate testset
        testset = self.generator.generate_with_langchain_docs(
            documents=documents,
            test_size=int(num_pairs * test_size),
            distributions={
                self.evolutions[e]: 1.0 / len(evolutions)
                for e in evolutions
            }
        )

        # Convert to our format
        qa_pairs = []
        for item in testset.test_data:
            qa_pair = {
                "question": item.user_input,
                "answer": item.reference,
                "metadata": {
                    "category": "FAQ-derived",
                    "intent": "generated_by_ragas",
                    "evolution_type": getattr(item, 'evolution_type', 'unknown'),
                    "context_chunks": item.context if hasattr(item, 'context') else [],
                    "confidence_score": 0.9,
                    "requires_handoff": False,
                    "tags": ["ragas_generated", "synthetic"],
                    "source_document": "ragas_generation",
                    "generated_at": datetime.now().isoformat(),
                }
            }
            qa_pairs.append(qa_pair)

        logger.info(f"Generated {len(qa_pairs)} Q&A pairs")
        return qa_pairs

    def save_dataset(self, qa_pairs: List[Dict[str, Any]], output_file: str) -> None:
        """Save dataset to file."""
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(qa_pairs, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved {len(qa_pairs)} pairs to {output_file}")


def create_synthetic_variants(
    qa_pairs: List[Dict[str, str]],
    num_variants: int = 3
) -> List[Dict[str, Any]]:
    """Create variants from original Q&A using simple heuristics."""

    # This is a fallback when RAGAS isn't available or for quick generation
    variants = []

    templates = {
        "how_can_i": "How can I {action}?",
        "what_is": "What's the process to {action}?",
        "where_do_i": "Where do I find {action}?",
        "why": "Why should I {action}?",
        "when": "When should I {action}?",
    }

    for pair in qa_pairs:
        question = pair.get("question", "")
        answer = pair.get("answer", "")

        # Extract action from question
        action = question.replace("How do I ", "").replace("?", "").lower()

        # Create variants
        for template_key, template in list(templates.items())[:num_variants]:
            variant_q = template.format(action=action) if "{action}" in template else template

            variant = {
                "question": variant_q,
                "answer": answer,
                "metadata": {
                    "category": "FAQ-derived",
                    "intent": action.replace(" ", "_"),
                    "difficulty": "medium",
                    "confidence_score": 0.85,
                    "requires_handoff": False,
                    "tags": ["variant", "faq_derived"],
                    "source_document": pair.get("metadata", {}).get("source", "unknown"),
                    "generated_at": datetime.now().isoformat(),
                }
            }
            variants.append(variant)

    return variants


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic Q&A using RAGAS TestsetGenerator"
    )
    parser.add_argument(
        "--documents",
        required=True,
        help="Input documents (Q&A JSON file)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output dataset file"
    )
    parser.add_argument(
        "--num-pairs",
        type=int,
        default=100,
        help="Number of Q&A pairs to generate (default: 100)"
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.5,
        help="Fraction of docs to use for generation (default: 0.5)"
    )
    parser.add_argument(
        "--evolutions",
        nargs="+",
        default=["simple", "reasoning"],
        help="RAGAS evolution types: simple, reasoning, multi_context"
    )

    args = parser.parse_args()

    print("\n🚀 Generating Q&A using RAGAS TestsetGenerator")
    print(f"   Input documents: {args.documents}")
    print(f"   Target pairs: {args.num_pairs}")
    print(f"   Evolutions: {args.evolutions}")
    print()

    try:
        generator = RAGASQAGenerator()

        # Load documents
        documents = generator.load_documents_from_qa(args.documents)

        # Generate testset
        qa_pairs = generator.generate_testset(
            documents=documents,
            num_pairs=args.num_pairs,
            test_size=args.test_size,
            evolutions=args.evolutions
        )

        # Save
        generator.save_dataset(qa_pairs, args.output)

    except ImportError:
        logger.error("RAGAS not available. Generating simple variants instead...")

        # Fallback: simple heuristic variants
        with open(args.documents, 'r', encoding='utf-8') as f:
            original = json.load(f)

        variants = create_synthetic_variants(original, num_variants=3)

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(variants, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Generated {len(variants)} variant pairs (simple mode)")

    print("\n✨ Generation complete!\n")


if __name__ == "__main__":
    main()
