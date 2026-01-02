"""Langfuse Dataset Synchronization for Ground Truth"""

import json
from typing import List, Dict, Optional
from langfuse import Langfuse

DATASET_NAME = "ground-truth-retrieval-eval"


def load_ground_truth_dataset(file_path: str) -> List[Dict[str, str]]:
    """Load ground truth dataset from JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def sync_dataset_to_langfuse(
    langfuse_client: Optional[Langfuse],
    ground_truth_data: List[Dict[str, str]],
    dataset_name: str = DATASET_NAME
) -> bool:
    """
    Sync ground truth dataset to Langfuse.

    Creates or updates dataset in Langfuse with ground truth Q&A pairs.

    Args:
        langfuse_client: Langfuse client instance (can be None if not available)
        ground_truth_data: List of items with "question" and "expected_chunk_answer"
        dataset_name: Name of dataset in Langfuse

    Returns:
        True if successful, False if Langfuse unavailable
    """
    if langfuse_client is None:
        print(f"⚠️ Langfuse not available, skipping dataset sync")
        return False

    try:
        # Check if dataset exists
        existing_dataset = langfuse_client.get_dataset(dataset_name)
        print(f"✅ Dataset '{dataset_name}' already exists in Langfuse ({len(existing_dataset.items)} items)")
        return True

    except Exception:
        # Dataset doesn't exist, create it
        try:
            print(f"📦 Creating dataset '{dataset_name}' in Langfuse...")
            langfuse_client.create_dataset(name=dataset_name)

            for item in ground_truth_data:
                langfuse_client.create_dataset_item(
                    dataset_name=dataset_name,
                    input={"question": item["question"]},
                    expected_output={"answer": item["expected_chunk_answer"]}
                )

            langfuse_client.flush()
            print(f"✅ Created dataset with {len(ground_truth_data)} items")
            return True

        except Exception as e:
            print(f"⚠️ Failed to create dataset in Langfuse: {e}")
            return False


def get_dataset_from_langfuse(
    langfuse_client: Optional[Langfuse],
    dataset_name: str = DATASET_NAME
) -> Optional[List[Dict]]:
    """
    Retrieve dataset from Langfuse.

    Args:
        langfuse_client: Langfuse client instance
        dataset_name: Name of dataset to retrieve

    Returns:
        List of dataset items or None if not available
    """
    if langfuse_client is None:
        return None

    try:
        dataset = langfuse_client.get_dataset(dataset_name)
        return dataset.items if dataset else None
    except Exception as e:
        print(f"⚠️ Failed to get dataset from Langfuse: {e}")
        return None
