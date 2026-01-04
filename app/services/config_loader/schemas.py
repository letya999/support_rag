"""
Pydantic schemas for config validation.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class NodeMeta(BaseModel):
    """Node metadata from config.yaml"""
    name: str
    version: str = "1.0.0"
    enabled: bool = True


class NodeConfig(BaseModel):
    """Base schema for node configuration"""
    node: NodeMeta
    parameters: Dict[str, Any] = Field(default_factory=dict)


class CacheConfig(BaseModel):
    """Cache configuration"""
    enabled: bool = True
    backend: str = "redis"
    redis_url: str = "redis://localhost:6379/0"
    ttl_seconds: int = 86400
    max_entries: int = 1000


class GlobalConfig(BaseModel):
    """Global pipeline settings"""
    default_language: str = "ru"
    confidence_threshold: float = 0.3
    debug_mode: bool = False


class PipelineNodeEntry(BaseModel):
    """Single node entry in pipeline"""
    name: str
    enabled: bool = True
    # Optional conditional edges
    on_hit: Optional[str] = None
    on_miss: Optional[str] = None
    on_auto_reply: Optional[str] = None
    on_handoff: Optional[str] = None


class PipelineConfig(BaseModel):
    """Main pipeline configuration schema"""
    version: str = "2.0"
    updated_at: Optional[str] = None
    global_config: GlobalConfig = Field(default_factory=GlobalConfig, alias="global")
    cache: CacheConfig = Field(default_factory=CacheConfig)
    pipeline: List[PipelineNodeEntry] = Field(default_factory=list)
    node_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        populate_by_name = True
