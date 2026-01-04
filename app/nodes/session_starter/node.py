from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.persistence import PersistenceManager
from app.cache.session_manager import SessionManager
from app.cache.cache_layer import get_cache_manager
from app.observability.tracing import observe

class SessionStarterNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Session loading logic.
        """
        user_id = state.get("user_id")
        session_id = state.get("session_id")
        
        if not user_id:
            return {}

        updates = {}
        
        # 0. Clean Input History (Remove system error artifacts)
        import json
        import os
        
        raw_history = state.get("conversation_history", [])
        if raw_history:
            # Load blacklist
            blacklist = []
            try:
                config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "history_blacklist.json")
                with open(config_path, "r", encoding="utf-8") as f:
                    blacklist = json.load(f)
            except Exception as e:
                print(f"⚠️ Error loading blacklist: {e}")
                blacklist = ["не смог обработать ваш вопрос"] # Fallback

            def is_clean(msg_content):
                if not msg_content: return True
                return not any(b_phrase in msg_content for b_phrase in blacklist)

            clean_history = [
                msg for msg in raw_history 
                if is_clean(msg.get("content", ""))
            ]
            
            if len(clean_history) != len(raw_history):
                updates["conversation_history"] = clean_history
        
        # 1. Load Long-Term Memory (Postgres)
        try:
            profile = await PersistenceManager.load_long_term_memory(user_id)
            updates["user_profile"] = profile
            
            # Load recent history
            history = await PersistenceManager.get_recent_sessions(user_id)
            updates["session_history"] = history
        except Exception as e:
            print(f"⚠️ Error loading persistence: {e}")
            updates["user_profile"] = {"error": str(e)}

        # 2. Manage Active Session (Redis)
        try:
            cache_manager = await get_cache_manager()
            if cache_manager.redis_client:
                session_manager = SessionManager(cache_manager.redis_client)
                current_session = await session_manager.get_session(user_id, session_id)
                
                if not current_session and session_id:
                    current_session = await session_manager.create_session(user_id, session_id)
        except Exception as e:
            print(f"⚠️ Error with Redis session: {e}")

        return updates

# For backward compatibility
load_session_node = SessionStarterNode()
