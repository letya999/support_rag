import asyncio
from app.pipeline.graph import rag_graph

async def test_graph():
    print("Graph structure:")
    for node in rag_graph.nodes:
        print(f"Node: {node}")
    
    # Simple check if start and end are there
    print("\nStarting simulation...")
    # We won't actually run it because it needs OpenAI and DB
    # but we can see if it's composed correctly.

if __name__ == "__main__":
    asyncio.run(test_graph())
