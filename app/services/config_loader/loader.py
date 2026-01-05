"""
Unified YAML configuration loader for nodes and pipeline.
Provides caching and nested parameter access.

Structure of pipeline_config.yaml:
  pipeline:
    - name: <node_name>
      enabled: <true/false>
  details:
    <node_name>:
      parameters: {...}
      config: {...}
"""
import yaml
import json
import re
import os
from pathlib import Path
from functools import lru_cache
from typing import Any, Optional, Dict


def env_var_constructor(loader, node):
    """
    Extracts the environment variable from the node's value.
    Format: ${VAR_NAME:-default_value}
    """
    pattern = re.compile(r"\$\{(\w+)(?::-(.*))?\}")
    value = loader.construct_scalar(node)
    match = pattern.match(value)
    if match:
        var_name, default_value = match.groups()
        return os.environ.get(var_name, default_value or "")
    return value

# Register the constructor for strings starting with ${
yaml.SafeLoader.add_implicit_resolver("!env", re.compile(r"\$\{(\w+)(?::-(.*))?\}"), None)
yaml.SafeLoader.add_constructor("!env", env_var_constructor)


NODES_DIR = Path(__file__).parent.parent.parent / "nodes"
PIPELINE_DIR = Path(__file__).parent.parent.parent / "pipeline"
SHARED_CONFIG_DIR = NODES_DIR / "_shared_config"


@lru_cache(maxsize=64)
def load_node_config(node_name: str) -> dict:
    """Load a node's local config.yaml with caching."""
    config_path = NODES_DIR / node_name / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=16)
def load_shared_config(config_name: str) -> dict:
    """Load a shared config from _shared_config directory."""
    if not config_name.endswith(".yaml"):
        config_name = f"{config_name}.yaml"
    config_path = SHARED_CONFIG_DIR / config_name
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_pipeline_config() -> dict:
    """Load the main pipeline configuration (YAML or JSON fallback)."""
    yaml_path = PIPELINE_DIR / "pipeline_config.yaml"
    json_path = PIPELINE_DIR / "pipeline_config.json"
    
    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    elif json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def clear_config_cache():
    """Clear all cached configurations for hot-reload."""
    load_node_config.cache_clear()
    load_shared_config.cache_clear()
    load_pipeline_config.cache_clear()


def get_node_enabled(node_name: str, pipeline_config: Optional[dict] = None) -> bool:
    """Check if a node is enabled in pipeline config."""
    if pipeline_config is None:
        pipeline_config = load_pipeline_config()
    
    for entry in pipeline_config.get("pipeline", []):
        if entry.get("name") == node_name:
            return entry.get("enabled", True)
    
    # Fallback to node's own config
    node_config = load_node_config(node_name)
    return node_config.get("node", {}).get("enabled", True)


def get_node_params(node_name: str, pipeline_config: Optional[dict] = None) -> dict:
    """
    Get node parameters from centralized pipeline_config.yaml details section.
    Falls back to node's own config.yaml if not found.
    
    Returns merged dict of: details[node].parameters + details[node].config
    """
    if pipeline_config is None:
        pipeline_config = load_pipeline_config()
    
    # Get from details section
    node_details = pipeline_config.get("details", {}).get(node_name, {})
    if node_details:
        # Merge parameters and config into flat dict
        result = {}
        result.update(node_details.get("parameters") or {})
        result.update(node_details.get("config") or {})
        return result
    
    # Fallback to node's own config - merge both parameters and config
    node_config = load_node_config(node_name)
    result = {}
    result.update(node_config.get("parameters") or {})
    result.update(node_config.get("config") or {})
    return result


def get_node_detail(node_name: str, section: str = "parameters") -> dict:
    """
    Get specific section from node details.
    section: "parameters" or "config"
    """
    pipeline_config = load_pipeline_config()
    node_details = pipeline_config.get("details", {}).get(node_name, {})
    return node_details.get(section) or {}


def get_global_param(param_name: str, default: Any = None) -> Any:
    """Get global parameter from pipeline_config.yaml details.global."""
    pipeline_config = load_pipeline_config()
    global_params = pipeline_config.get("details", {}).get("global", {}).get("parameters", {})
    return global_params.get(param_name, default)


def get_cache_config() -> dict:
    """Get cache configuration from pipeline_config.yaml details.cache."""
    pipeline_config = load_pipeline_config()
    return pipeline_config.get("details", {}).get("cache", {}).get("parameters", {})


def _get_nested(data: dict, path: str, default: Any = None) -> Any:
    """Get nested value from dict using dot notation."""
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
        if value is None:
            return default
    return value


def get_param(node_name: str, param_path: str, default: Any = None) -> Any:
    """Get a nested parameter from node config using dot notation."""
    config = load_node_config(node_name)
    return _get_nested(config, param_path, default)


def get_shared_param(config_name: str, param_path: str, default: Any = None) -> Any:
    """Get a nested parameter from shared config using dot notation."""
    config = load_shared_config(config_name)
    return _get_nested(config, param_path, default)
