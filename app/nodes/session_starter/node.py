from typing import Dict, Any
from app.pipeline.state import State
from app.nodes.persistence import PersistenceManager
from app.cache.session_manager import SessionManager
from app.cache.cache_layer import get_cache_manager

async def load_session_node(state: State) -> Dict[str, Any]:
    """
    Node: Loads user session and long-term memory.
    """
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    
    if not user_id:
        # If no user_id provided (e.g. testing), just return empty
        return {}

    updates = {}
    
    # 1. Load Long-Term Memory (Postgres)
    try:
        profile = await PersistenceManager.load_long_term_memory(user_id)
        updates["user_profile"] = profile
        
        # Load recent history
        history = await PersistenceManager.get_recent_sessions(user_id)
        updates["session_history"] = history
    except Exception as e:
        print(f"⚠️ Error loading persistence: {e}")
        # Don't fail the pipeline for this
        updates["user_profile"] = {"error": str(e)}

    # 2. Manage Active Session (Redis)
    try:
        cache_manager = await get_cache_manager()
        if cache_manager.redis_client:
            session_manager = SessionManager(cache_manager.redis_client)
            
            # Get or create session
            # For now, we assume one active session or use provided id
            current_session = await session_manager.get_session(user_id, session_id)
            
            if not current_session:
                # Create new if explicit session_id or just ephemeral?
                # For Stage 1, we just try to load. If it doesn't exist, we might create it 
                # if we have a session_id. If session_id is None, maybe we don't force create yet.
                if session_id:
                     current_session = await session_manager.create_session(user_id, session_id)
            
            # If we decided to update extracted entities from cache, we would do it here
            # updates["extracted_entities"] = current_session.extracted_entities
            
    except Exception as e:
        print(f"⚠️ Error with Redis session: {e}")

    return updates
