import sys
import os

sys.path.insert(0, os.getcwd())

def verify_graph_build():
    print("🏗️ Verifying RAG Pipeline Graph Build...")
    try:
        from app.pipeline.graph import rag_graph
        print("✅ Graph compiled successfully!")
        
        # Optional: Print graph nodes to verify structure
        print(f"   Graph Nodes: {list(rag_graph.nodes.keys())}")
        
    except Exception as e:
        print(f"❌ Graph compilation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    verify_graph_build()
