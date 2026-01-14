from typing import Dict, Any, List, Optional
from app.nodes.base_node import BaseNode
from app._shared_config.history_filter import filter_conversation_history
from app.services.cache.manager import get_cache_manager
from app.services.cache.session_manager import SessionManager
from app.storage.persistence import PersistenceManager
from app.logging_config import logger
from app.services.config_loader.loader import get_node_params

class SessionStarterNode(BaseNode):
    """
    Session loading node with lazy loading optimizations.
    
    Contracts:
        Input:
            Required:
                - user_id (str): User identifier
                - session_id (str): Session identifier
            Optional: None
        
        Output:
            Guaranteed:
                - conversation_history (List[Dict]): Messages from current session
            Conditional:
                - user_profile (Dict): User profile if enabled
                - _session_history_loader (Callable): Lazy loader for previous sessions
                - attempt_count (int): Counter for processing attempts
                - extracted_entities (Dict): Extracted entities from session
                - _session_metadata (Dict): Session metadata for debugging
    """
    
    INPUT_CONTRACT = {
        "required": ["user_id", "session_id"],
        "optional": []
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["conversation_history"],
        "conditional": [
            "user_profile",
            "_session_history_loader", 
            "attempt_count",
            "extracted_entities",
            "_session_metadata",
            "_session_metadata",
            "clarification_context",
            "clarified_doc_ids"
        ]
    }
    
    def __init__(self):
        super().__init__("session_starter")
        params = get_node_params("session_starter")
        self.params = params if params is not None else {}

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute session loading logic."""
        user_id = state.get("user_id")
        session_id = state.get("session_id")
        
        if not user_id:
            return {"conversation_history": []}

        updates = {}
        
        # 0. Clean Input History (Remove system error artifacts)
        # Note: If reducers are used (add_messages), this might need adjustment to avoid duplication
        # For now, we assume overwrite behavior or fresh state
        
        try:
            # 1. Load conversation_history (Redis-first with PostgreSQL fallback)
            max_history = self.params.get("max_history_messages", 5)
            
            updates["conversation_history"] = await self._load_history_hybrid(
                user_id=user_id,
                session_id=session_id,
                max_messages=max_history
            )
            
        except Exception as e:
            logger.error(
                "Failed to load conversation history", 
                extra={"session_id": session_id, "error": str(e)}
            )
            updates["conversation_history"] = []

        # 2. Load User Profile (Lazy or Eager based on config)
        # ...
        params = getattr(self, "params", {})
        load_profile = params.get("load_user_profile", True)
        
        if load_profile:
             try:
                updates["user_profile"] = await self._load_user_profile(user_id)
             except Exception as e:
                logger.warning("Error loading user profile", extra={"user_id": user_id, "error": str(e)})
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
            
            # Restore Clarification Context
            if active_session.clarification_context:
                updates["clarification_context"] = active_session.clarification_context
            
            # Restore Clarified Doc IDs
            if active_session.clarified_doc_ids:
                updates["clarified_doc_ids"] = active_session.clarified_doc_ids
            
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
            if cache_manager.redis.is_available():
                session_manager = SessionManager(cache_manager.redis.client)
                current_session = await session_manager.get_session(user_id, session_id)
                
                if not current_session and session_id:
                    current_session = await session_manager.create_session(user_id, session_id)
                
                return current_session
        except Exception as e:
            logger.error("Error with Redis session", extra={"user_id": user_id, "session_id": session_id, "error": str(e)})
            return None

    async def _load_history_hybrid(
        self, 
        user_id: str,
        session_id: str, 
        max_messages: int
    ) -> List[Dict[str, Any]]:
        """
        Load conversation history with hybrid strategy.
        
        Strategy:
            1. Redis: ONLY current session messages (hot cache)
            2. PostgreSQL session: current session messages if Redis miss
            3. PostgreSQL cross-session: ALWAYS load recent messages from other sessions for context
        
        Final history = [cross-session context (older)] + [current session messages (recent)]
        
        Args:
            user_id: User identifier (for cross-session history)
            session_id: Current session identifier (for Redis cache key)
            max_messages: Max messages to load
        
        Returns:
            List of conversation messages in format:
            [{"role": "user", "content": "...", "created_at": "..."}, ...]
        """
        current_session_messages = []
        
        # Step 1: Try Redis first for CURRENT SESSION only
        try:
            cache_manager = await get_cache_manager()
            if cache_manager.redis.is_available():
                session_manager = SessionManager(cache_manager.redis.client)
                redis_messages = await session_manager.get_recent_messages(
                    session_id, 
                    limit=max_messages
                )
                
                if redis_messages:
                    logger.info(
                        "✅ Current session loaded from Redis (hot cache)", 
                        extra={
                            "session_id": session_id, 
                            "messages": len(redis_messages),
                            "source": "redis"
                        }
                    )
                    current_session_messages = redis_messages
                    
        except Exception as e:
            logger.warning(
                "Redis cache lookup failed", 
                extra={"session_id": session_id, "error": str(e)}
            )
        
        # Step 2: If Redis miss, load CURRENT SESSION from PostgreSQL
        if not current_session_messages:
            logger.info(
                "🔄 Redis miss - loading current session from PostgreSQL", 
                extra={"session_id": session_id, "source": "postgresql"}
            )
            
            raw_session_history = await PersistenceManager.get_session_messages(
                session_id=session_id,
                limit=max_messages
            )
            
            if raw_session_history:
                current_session_messages = filter_conversation_history(raw_session_history)
                
                # Warm up Redis ONLY with current session messages
                try:
                    cache_manager = await get_cache_manager()
                    if cache_manager.redis.is_available():
                        session_manager = SessionManager(cache_manager.redis.client)
                        
                        for msg in current_session_messages[-50:]:
                            await session_manager.add_message(
                                session_id, 
                                msg.get("role", "user"), 
                                msg.get("content", "")
                            )
                        
                        logger.info(
                            "💾 Warmed up Redis with current session",
                            extra={
                                "session_id": session_id,
                                "cached_messages": len(current_session_messages)
                            }
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to warm up Redis (non-critical)",
                        extra={"session_id": session_id, "error": str(e)}
                    )
        
        # Step 3: ALWAYS load cross-session context from PostgreSQL (other sessions)
        # This gives context even when user switches sessions
        cross_session_context = []
        try:
            # Load recent messages from ALL user's sessions
            all_messages = await PersistenceManager.get_user_recent_messages(
                user_id=user_id,
                limit=max_messages * 2  # Get more for better context
            )
            
            if all_messages:
                # Filter out messages from current session (already loaded)
                # Keep only messages from OTHER sessions for context
                cross_session_context = [
                    msg for msg in all_messages 
                    if msg.get("session_id") != session_id
                ][:max_messages // 2]  # Use half of limit for context
                
                if cross_session_context:
                    logger.info(
                        "📚 Loaded cross-session context from PostgreSQL",
                        extra={
                            "user_id": user_id,
                            "context_messages": len(cross_session_context),
                            "excluded_current_session": session_id
                        }
                    )
        except Exception as e:
            logger.warning(
                "Failed to load cross-session context (non-critical)",
                extra={"user_id": user_id, "error": str(e)}
            )
        
        # Step 4: Combine histories - context first, then current session
        # This maintains chronological order with older context + recent session
        final_history = cross_session_context + current_session_messages
        
        # Trim to max_messages if needed
        if len(final_history) > max_messages:
            final_history = final_history[-max_messages:]
        
        logger.info(
            "📖 Final history assembled",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "total_messages": len(final_history),
                "current_session": len(current_session_messages),
                "cross_session_context": len(cross_session_context)
            }
        )
        
        return filter_conversation_history(final_history)

# For backward compatibility
load_session_node = SessionStarterNode()
