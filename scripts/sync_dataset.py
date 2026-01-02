import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from langfuse import Langfuse
from app.ground_truth.dataset_sync import sync_dataset_to_langfuse, load_ground_truth_dataset

def main():
    # Load credentials from .env if needed
    # (Assuming they are set in environment variables already)
    
    langfuse = Langfuse()
    
    dataset_path = os.path.join("datasets", "ground_truth_dataset.json")
    if not os.path.exists(dataset_path):
        print(f"❌ Dataset not found at {dataset_path}")
        return

    print(f"📂 Loading dataset from {dataset_path}...")
    ground_truth_data = load_ground_truth_dataset(dataset_path)
    
    print(f"🚀 Syncing to Langfuse...")
    success = sync_dataset_to_langfuse(langfuse, ground_truth_data)
    
    if success:
        print("✅ Dataset synced successfully!")
    else:
        print("❌ Dataset sync failed.")

if __name__ == "__main__":
    main()
