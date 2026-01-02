#!/usr/bin/env python3
"""
Ground Truth Retrieval Evaluation Script

Evaluates retrieval performance using ground truth dataset.
Logs metrics to Langfuse for monitoring.
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from app.ground_truth.evaluator import evaluate_ground_truth


async def main():
    """Main entry point"""
    # Initialize Langfuse if available
    langfuse_client = None
    try:
        from langfuse import Langfuse
        langfuse_client = Langfuse()
        print("✅ Langfuse initialized\n")
    except Exception as e:
        print(f"⚠️ Langfuse not available: {e}\n")

    # Run evaluation
    results = await evaluate_ground_truth(
        langfuse_client=langfuse_client,
        ground_truth_file="ground_truth_dataset.json",
        top_k=3,
    )

    if results:
        print(f"✅ Evaluation complete!")
    else:
        print(f"❌ Evaluation failed")


if __name__ == "__main__":
    asyncio.run(main())
