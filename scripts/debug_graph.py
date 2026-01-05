import sys
import os
import traceback

sys.path.append(os.getcwd())

print("Attempting to build graph...")
try:
    from app.pipeline.graph import rag_graph
    # Verify graph structure
    print(f"✅ Graph built: {rag_graph}")
except Exception as e:
    traceback.print_exc()
    print("❌ Failed to build graph")
