from typing import List, Dict, Any, Optional
from app.nodes.base_node import BaseNode
from app.storage.persistence import PersistenceManager
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

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Session loading logic with lazy loading optimizations.

        Contracts:
            - Required Inputs: `user_id` (str), `session_id` (str)
            - Optional Inputs: None
            - Guaranteed Outputs: `conversation_history` (List[Dict]), `user_profile` (Dict, if enabled), `_session_history_loader` (Callable), `attempt_count` (int, if persisted), `extracted_entities` (optional), `_session_metadata` (optional)
        """
        user_id = state.get("user_id")
        session_id = state.get("session_id")
        
        if not user_id:
            return {}

        updates = {}
        
        # 0. Clean Input History (Remove system error artifacts)
        # Note: If reducers are used (add_messages), this might need adjustment to avoid duplication
        # For now, we assume overwrite behavior or fresh state
        
        try:
            # 1. Load conversation_history from DB (current session)
            # We strictly enforce DB as the single source of truth for history
            max_history = self.params["max_history_messages"]
            raw_history_db = await PersistenceManager.get_session_messages(
                session_id=session_id,
                limit=max_history
            )

            if raw_history_db:
                clean_history = filter_conversation_history(raw_history_db)
                updates["conversation_history"] = clean_history
                print(f"✅ session_starter: Loaded {len(clean_history)} messages from DB")
            else:
                # No history in DB means new session or empty state
                updates["conversation_history"] = []
                print(f"ℹ️ session_starter: No messages found in DB (new session).")

        except Exception as e:
            print(f"⚠️ Failed to load conversation history from DB: {e}")
            updates["conversation_history"] = []

        # 2. Load User Profile (Lazy or Eager based on config)
        # ...
        params = getattr(self, "params", {})
        load_profile = params.get("load_user_profile", True)
        
        if load_profile:
             try:
                updates["user_profile"] = await self._load_user_profile(user_id)
             except Exception as e:
                print(f"⚠️ Error loading profile: {e}")
                updates["user_profile"] = {"error": str(e)}

        # 3. Lazy Load Session History (Previous sessions)
        # We pass a callable that PromptRouting can use
        updates["_session_history_loader"] = lambda: self._load_session_history_sync(user_id, session_id)

        # 3. Manage Active Session (Redis)
        # Load state from active session to ensure continuity
        active_session = await self._ensure_redis_session(user_id, session_id)
        
        if active_session:
            # Restore ONLY persistent context (counters and entities)
            # dialog_state is managed by dialog_analysis and state_machine for EACH new request
            # to avoid carrying over stale states like SAFETY_VIOLATION from previous interactions
            
            updates["attempt_count"] = active_session.attempt_count
            
            if active_session.extracted_entities:
                updates["extracted_entities"] = active_session.extracted_entities
            
            # Store session metadata for debugging and context (not operational state)
            updates["_session_metadata"] = {
                "previous_dialog_state": active_session.dialog_state,
                "session_created_at": getattr(active_session, "created_at", None),
            }

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
        # Load max_session_history from config
        max_sessions = self.params["max_session_history"]
        return PersistenceManager.get_user_recent_sessions(user_id, limit=max_sessions)

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
