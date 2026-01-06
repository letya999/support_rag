from typing import List, Dict, Any, Optional
from app.nodes.base_node import BaseNode
from app.nodes.persistence import PersistenceManager
from app.cache.session_manager import SessionManager
from app.cache.cache_layer import get_cache_manager
from app.observability.tracing import observe
from app.nodes._shared_config.history_filter import filter_conversation_history

from app.services.config_loader.loader import get_node_params

class SessionStarterNode(BaseNode):
    def __init__(self):
        super().__init__("session_starter")
        params = get_node_params("session_starter")
        self.params = params if params is not None else {}

    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Session loading logic with lazy loading optimizations.
        """
        user_id = state.get("user_id")
        session_id = state.get("session_id")
        
        if not user_id:
            return {}

        updates = {}
        
        # 0. Clean Input History (Remove system error artifacts)
        # Note: If reducers are used (add_messages), this might need adjustment to avoid duplication
        # For now, we assume overwrite behavior or fresh state
        raw_history = state.get("conversation_history", [])
        if raw_history:
            clean_history = filter_conversation_history(raw_history)
            
            if len(clean_history) != len(raw_history):
                updates["conversation_history"] = clean_history
        
        # 1. Load User Profile (Lazy or Eager based on config)
        # In this implementation we prep the loader or load based on flag
        # For Phase 3.2 we default to lazy via loader or direct if needed immediately?
        # Roadmap says: Load user_profile ONLY IF NEEDED (params check)
        
        # Safe access to params
        params = getattr(self, "params", {})
        load_profile = params.get("load_user_profile", True)
        
        if load_profile:
             # If we want to support lazy loading properly, the consumer node needs to call the loader.
             # But existing consumers expect "user_profile" data.
             # Roadmap suggests: just load it here if flag is True. 
             # "Загружаем user_profile только если нужен"
             try:
                updates["user_profile"] = await self._load_user_profile(user_id)
             except Exception as e:
                print(f"⚠️ Error loading profile: {e}")
                updates["user_profile"] = {"error": str(e)}

        # 2. Lazy Load Session History
        # We pass a callable that PromptRouting can use
        updates["_session_history_loader"] = lambda: self._load_session_history_sync(user_id, session_id)
        
        # We DO NOT load session_history eagerly anymore to save time
        # updates["session_history"] = ... (REMOVED)

        # 3. Manage Active Session (Redis)
        # Load state from active session to ensure continuity
        active_session = await self._ensure_redis_session(user_id, session_id)
        
        if active_session:
            # Restore state context
            updates["dialog_state"] = active_session.dialog_state
            updates["attempt_count"] = active_session.attempt_count
            
            # Restore other context if needed
            if active_session.extracted_entities:
                updates["extracted_entities"] = active_session.extracted_entities


        return updates

    async def _load_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Load user profile from persistence."""
        return await PersistenceManager.load_long_term_memory(user_id)

    def _load_session_history_sync(self, user_id: str, session_id: Any) -> List[Dict[str, Any]]:
        """
        Sync wrapper for loading session history. 
        Note: PersistenceManager.get_recent_sessions is async.
        We cannot easily return a sync lambda for an async operation unless we run it in event loop.
        However, the roadmap implies a lambda.
        If PromptRouting is async, it can await a coroutine.
        Let's return an async function (coroutine function) or a partial.
        """
        # We'll return a coroutine object or function
        # But lambda cannot be async easily in that syntax without async def.
        # We will store the coroutine FUNCTION.
        import asyncio
        # Actually better to return an async lambda
        return PersistenceManager.get_recent_sessions(user_id)

    async def _ensure_redis_session(self, user_id: str, session_id: str) -> Optional[Any]:
        try:
            cache_manager = await get_cache_manager()
            if cache_manager.redis_client:
                session_manager = SessionManager(cache_manager.redis_client)
                current_session = await session_manager.get_session(user_id, session_id)
                
                if not current_session and session_id:
                    current_session = await session_manager.create_session(user_id, session_id)
                
                return current_session
        except Exception as e:
            print(f"⚠️ Error with Redis session: {e}")
            return None

# For backward compatibility
load_session_node = SessionStarterNode()
