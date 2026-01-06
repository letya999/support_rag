import asyncio
import sys
import os
import uuid
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from app.storage.persistence import PersistenceManager
from app.nodes.session_starter.node import SessionStarterNode
from app.nodes.archive_session.node import ArchiveSessionNode

from app.settings import settings

async def test_flow():
    print(f"DEBUG: DATABASE_URL={settings.DATABASE_URL}")
    session_id = f"test_verify_{uuid.uuid4().hex[:8]}"
    user_id = "test_user_verify"
    
    print(f"🔹 Testing with Session ID: {session_id}")

    # 1. Test Direct Persistence Layer
    print("\n--- 1. Testing PersistenceManager Direct ---")
    
    # Save User Msg
    await PersistenceManager.save_message(session_id, user_id, "user", "Hello DB")
    print("✅ Saved user message")
    
    # Save Bot Msg
    await PersistenceManager.save_message(session_id, user_id, "assistant", "Hello User")
    print("✅ Saved assistant message")
    
    # Update Session
    await PersistenceManager.update_session(session_id, user_id, "test_script", "active")
    print("✅ Updated session metadata")
    
    # Read Back
    msgs = await PersistenceManager.get_session_messages(session_id)
    print(f"📖 Read back {len(msgs)} messages")
    for m in msgs:
        print(f"   - {m['role']}: {m['content']}")
        
    assert len(msgs) == 2, "Should have 2 messages"
    assert msgs[0]['content'] == "Hello DB"
    
    # 2. Test Session Starter Node (Reading)
    print("\n--- 2. Testing SessionStarterNode (Read) ---")
    starter = SessionStarterNode()
    state_input = {
        "user_id": user_id,
        "session_id": session_id,
        "conversation_history": [] # Simulate empty request history
    }
    
    result = await starter.execute(state_input)
    loaded_history = result.get("conversation_history", [])
    print(f"🔍 SessionStarter loaded {len(loaded_history)} messages")
    
    assert len(loaded_history) == 2, "SessionStarter should load 2 messages from DB"
    assert loaded_history[0]['content'] == "Hello DB"
    
    # 3. Test Archive Session Node (Writing)
    print("\n--- 3. Testing ArchiveSessionNode (Write) ---")
    archive = ArchiveSessionNode()
    state_archive = {
        "user_id": user_id,
        "session_id": session_id,
        "question": "How are you?",
        "answer": "I am fine, thanks.",
        "confidence": 0.99,
        "dialog_state": "active"
    }
    
    await archive.execute(state_archive)
    print("✅ ArchiveSession executed")
    
    # Verify via DB read
    msgs_after = await PersistenceManager.get_session_messages(session_id)
    print(f"📖 History after archive: {len(msgs_after)} messages")
    
    assert len(msgs_after) == 4, "Should have 4 messages now (2 previous + user + assistant)"
    assert msgs_after[2]['content'] == "How are you?"
    assert msgs_after[3]['content'] == "I am fine, thanks."
    
    print("\n🎉 ALL CHECKS PASSED SUCCESSFULLY")

if __name__ == "__main__":
    try:
        asyncio.run(test_flow())
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
