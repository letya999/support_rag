
import asyncio
import json
import logging
import uuid
from app.pipeline.graph import rag_graph
from app.services.config_loader.loader import load_shared_config

# Mock IdentityManager to avoid DB lookups or complex setup
class MockIdentityManager:
    @staticmethod
    async def resolve_identity(*args, **kwargs):
        return str(uuid.uuid4())

# Monkey patch IdentityManager
from app.services.identity.manager import IdentityManager
IdentityManager.resolve_identity = MockIdentityManager.resolve_identity

import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def run_debug():
    question = "Напомни, есть ли у вас скидки? На сайте не нашел"
    session_id = "debug_session"
    trace_id = str(uuid.uuid4())
    
    global_config = load_shared_config("global")
    confidence_threshold = global_config.get("parameters", {}).get("confidence_threshold", 0.3)
    
    input_state = {
        "question": question,
        "conversation_context": [],
        "user_id": "debug_user",
        "session_id": session_id,
        "hybrid_used": True,
        "confidence_threshold": confidence_threshold
    }

    print(f"DEBUG: Starting graph execution with questions: {question}")
    
    final_state = {}
    
    async for event in rag_graph.astream_events(
        input_state, 
        version="v1",
        config={"callbacks": [], "run_name": "api_chat_stream"}
    ):
        kind = event["event"]
        tags = event.get("tags", [])
        name = event.get("name", "")
        
        if kind == "on_chat_model_stream":
            if "generation_llm" in tags or "clarification_llm" in tags:
                content = event["data"]["chunk"].content
                print(f"TOKEN: {content}")
        
        elif kind == "on_chain_stream" and name == "LangGraph":
            # Emulate production buffering
            final_state.update(event["data"]["chunk"])

        elif kind == "on_chain_end":
            if name == "api_chat_stream":
                # FIX: Use update instead of overwrite
                output = event["data"]["output"]
                if isinstance(output, dict):
                    final_state.update(output)
                print("GRAPH ENDED. Final State captured.")
            else:
                 # Print output of nodes to trace flow
                 output = event["data"].get("output")
                 if output:
                     if isinstance(output, dict):
                         print(f"NODE {name} ENDED. Output keys: {list(output.keys())}")
                         if "action" in output:
                             print(f"  Action: {output['action']}")
                         if "answer" in output:
                             print(f"  Answer: {output['answer']}")
                         if "confidence" in output:
                             print(f"  Confidence: {output['confidence']}")
                     else:
                         print(f"NODE {name} ENDED. Output: {output}")

    print("\nFINAL DATA:")
    print(f"Question: {question}")
    print(f"Answer: '{final_state.get('answer', '')}'")
    print(f"Confidence: {final_state.get('confidence')}")
    print(f"Sources: {len(final_state.get('best_doc_metadata', []) or [])}")

if __name__ == "__main__":
    asyncio.run(run_debug())
