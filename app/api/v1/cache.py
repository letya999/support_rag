from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
from redis import asyncio as aioredis
from app.api.v1.models import Envelope, MetaResponse
from app.settings import settings
from app.services.cache.manager import get_cache_manager

router = APIRouter(tags=["Cache"])

class CacheStatus(BaseModel):
    memory_usage_mb: float
    total_keys: int
    hit_rate: Optional[float] = None
    connected: bool

@router.get("/cache/messages", response_model=Envelope[List[Dict[str, Any]]])
async def get_cached_messages(
    request: Request, 
    user_id: str, 
    limit: int = 10
):
    """
    Get session state from Redis.
    Note: Actual message content is currently stored in Postgres, not Redis.
    This endpoint returns the active session state and metadata.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    if not settings.REDIS_URL:
        raise HTTPException(status_code=500, detail="Redis URL not configured")
    
    try:
        manager = await get_cache_manager()
        redis = manager.redis
        
        # 1. Get active session ID
        session_id_bytes = await redis.get(f"user:active_session:{user_id}")
        session_id = session_id_bytes.decode() if session_id_bytes else None
        
        results = []
        extra_info = {"active_session_id": session_id}
        
        if session_id:
            # 2. Get Session Data
            session_key = f"session:{session_id}"
            session_data = await redis.get(session_key)
            
            if session_data:
                # We return the session state as a "message" for debugging purposes
                # since messages are not in cache.
                try:
                    session_json = json.loads(session_data)
                    results.append({
                        "role": "system",
                        "content": f"Session State: {session_json.get('dialog_state')}",
                        "timestamp": session_json.get("last_activity_time"),
                        "metadata": session_json
                    })
                except:
                    results.append({"role": "error", "content": "Failed to parse session data"})
        
        return Envelope(
            data=results,
            meta=MetaResponse(
                trace_id=trace_id,
                extra=extra_info
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cache", response_model=Envelope[Dict[str, str]])
async def clear_cache(
    request: Request,
    user_id: Optional[str] = None
):
    """
    Clear cache for user or all.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        manager = await get_cache_manager()
        redis = manager.redis
        count = 0
        
        if user_id and user_id != "all":
            # Clear active session pointer and session data
            session_id_bytes = await redis.get(f"user:active_session:{user_id}")
            if session_id_bytes:
                session_id = session_id_bytes.decode()
                await redis.delete(f"session:{session_id}")
                await redis.delete(f"user:active_session:{user_id}")
                count = 1
        else:
            # Clear all session keys
            # Using keys() is not recommended for production but fine for debug endpoint
            # We should probably use manager.clear() if available or implement scan
            pass # TODO: Implement safe clear all
            
            # For now, just a placeholder as safer not to wipe everything blindly
            # unless explicitly implemented in manager
        
        return Envelope(
            data={"status": "cleared", "count": str(count)},
            meta=MetaResponse(trace_id=trace_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/status", response_model=Envelope[CacheStatus])
async def get_cache_status(request: Request):
    """
    Get Redis status/metrics.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        manager = await get_cache_manager()
        health = await manager.health_check()
        
        # Stats from manager
        stats = manager.get_stats()
        hit_rate = 0.0
        
        if stats:
             total = stats.total_requests
             hits = stats.cache_hits
             if total > 0:
                 hit_rate = hits / total
        
        # Redis info
        info = {}
        if manager.redis.is_available():
            # This calls the method we just added to RedisConnector
            info = await manager.redis.info("memory")
            
        used_memory = info.get("used_memory", 0)
        
        return Envelope(
            data=CacheStatus(
                memory_usage_mb=round(used_memory / 1024 / 1024, 2),
                total_keys=0, 
                hit_rate=hit_rate,
                connected=health.get("status") == "healthy"
            ),
            meta=MetaResponse(trace_id=trace_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
