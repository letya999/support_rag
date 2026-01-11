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
    Get recent messages from Redis session cache.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    if not settings.REDIS_URL:
        raise HTTPException(status_code=500, detail="Redis URL not configured")
    
    try:
        redis = await aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        key = f"user:{user_id}"
        data = await redis.get(key)
        await redis.close()
        
        messages = []
        if data:
            session = json.loads(data)
            msgs = session.get("messages", [])
            # Return last N
            for m in msgs[-limit:]:
                messages.append({
                    "role": m.get("role"),
                    "content": m.get("content"),
                    "timestamp": m.get("timestamp")
                })
                
        return Envelope(
            data=messages,
            meta=MetaResponse(trace_id=trace_id)
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
    if not settings.REDIS_URL:
        raise HTTPException(status_code=500, detail="Redis URL not configured")
        
    try:
        redis = await aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        count = 0
        
        if user_id and user_id != "all":
            key = f"user:{user_id}"
            if await redis.delete(key):
                count = 1
        else:
            # Clear all session keys (user:*)
            # Be careful not to clear others if shared redis?
            # Plan says "Clear cache". "user:*" is safe enough for this purpose.
            keys = await redis.keys("user:*")
            if keys:
                count = await redis.delete(*keys)
                
            # Also clear FAQ cache? Plan says "Cache Debugging", implies global cache too.
            # But "user_id" param implies session cache.
            # If "all" is passed, we might want to clear FAQ cache too.
            if user_id == "all":
                faq_keys = await redis.keys("faq_cache:*")
                if faq_keys:
                    await redis.delete(*faq_keys)
        
        await redis.close()
        
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
        
        # Stats from manager (FAQ cache)
        stats = manager.get_stats() # Returns CacheStats Pydantic model
        hit_rate = 0.0
        
        if stats:
            # Fix: access fields directly, stats is not a dict
            total = stats.total_requests
            hits = stats.cache_hits
            if total > 0:
                hit_rate = hits / total
        
        # Redis info
        info = {}
        if manager.redis.is_available():
            info = await manager.redis.info("memory")
            
        used_memory = info.get("used_memory", 0)
        
        return Envelope(
            data=CacheStatus(
                memory_usage_mb=round(used_memory / 1024 / 1024, 2),
                total_keys=0, # Hard to count efficiently without scan
                hit_rate=hit_rate,
                connected=health.get("status") == "healthy"
            ),
            meta=MetaResponse(trace_id=trace_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
