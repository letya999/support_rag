import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.nodes.aggregation.lightweight import lightweight_aggregation_node
from app.nodes.aggregation.llm import llm_aggregation_node
from app.config.conversation_config import conversation_config

async def test_aggregation():
    # Setup state with history
    state = {
        "question": "what is its status?",
        "session_history": [
            {"role": "user", "content": "I placed an order #12345 yesterday."},
            {"role": "assistant", "content": "I see it."},
            {"role": "user", "content": "is it shipped?"}
        ],
        "conversation_config": {}
    }

    print("--- Testing Lightweight Aggregation ---")
    res_lw = lightweight_aggregation_node(state)
    print(f"Result: {res_lw}")

    print("\n--- Testing LLM Aggregation ---")
    try:
        res_llm = await llm_aggregation_node(state)
        print(f"Result: {res_llm}")
    except Exception as e:
        print(f"LLM Aggregation failed (expected if no API key): {e}")

if __name__ == "__main__":
    asyncio.run(test_aggregation())
