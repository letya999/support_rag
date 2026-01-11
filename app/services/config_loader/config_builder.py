import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class PipelineConfigBuilder:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.nodes_dir = root_dir / "app" / "nodes"
        self.pipeline_dir = root_dir / "app" / "pipeline"
        self.shared_config_dir = self.nodes_dir / "_shared_config"

    def load_pipeline_order(self) -> List[str]:
        """Load pipeline order from YAML config file."""
        order_file = self.pipeline_dir / "pipeline_order.yaml"
        if not order_file.exists():
            logger.warning(f"Warning: {order_file} not found. Using default order.")
            return [
                "session_starter", "check_cache", "dialog_analysis", "state_machine",
                "aggregation", "easy_classification", "classify", "metadata_filtering",
                "expand_query", "hybrid_search", "retrieve", "lexical_search", "fusion",
                "reranking", "multihop", "routing", "prompt_routing", "generation",
                "archive_session", "store_in_cache"
            ]
        
        with open(order_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("pipeline_order", [])

    def load_shared_configs(self) -> Dict[str, Any]:
        """Load all shared configs from _shared_config directory."""
        shared_configs = {}
        if not self.shared_config_dir.exists():
            return shared_configs
        
        for config_file in self.shared_config_dir.glob("*.yaml"):
            if config_file.name == "intents_registry.yaml":
                continue
            
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config_name = config_file.stem
                    shared_configs[config_name] = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Error reading shared config {config_file}: {e}")
        
        return shared_configs

    def generate_full_config(self) -> Dict[str, Any]:
        pipeline_config_path = self.pipeline_dir / "pipeline_config.yaml"
        
        # 0. Load pipeline order from config
        pipeline_order = self.load_pipeline_order()
        
        # 0.1. Load shared configs
        shared_configs = self.load_shared_configs()
        
        # 1. Collect all node configs from app/nodes/
        raw_node_configs = {}
        name_to_folder = {}
        
        if not self.nodes_dir.exists():
            logger.error(f"Error: NODES_DIR {self.nodes_dir} not found.")
            return {}

        for node_dir in self.nodes_dir.iterdir():
            if node_dir.is_dir() and not node_dir.name.startswith(("_", ".")):
                config_file = node_dir / "config.yaml"
                if config_file.exists():
                    try:
                        with open(config_file, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}
                            raw_node_configs[node_dir.name] = data
                            node_name = data.get("node", {}).get("name", node_dir.name)
                            name_to_folder[node_name] = node_dir.name
                    except Exception as e:
                        logger.error(f"Error reading {config_file}: {e}")

        # 2. Build Pipeline Section
        pipeline = []
        processed_nodes = set()
        
        for node_name in pipeline_order:
            enabled = False
            folder_name = name_to_folder.get(node_name, node_name)
            
            if folder_name in raw_node_configs:
                enabled = raw_node_configs[folder_name].get("node", {}).get("enabled", True)
                processed_nodes.add(node_name)
            elif node_name in ["check_cache", "store_in_cache"]:
                enabled = True
                processed_nodes.add(node_name)
            else:
                enabled = False
            
            pipeline.append({
                "name": node_name,
                "enabled": enabled
            })

        # Add any extra nodes
        for node_name, folder_name in sorted(name_to_folder.items()):
            if node_name not in processed_nodes:
                pipeline.append({
                    "name": node_name,
                    "enabled": raw_node_configs[folder_name].get("node", {}).get("enabled", True)
                })

        # 3. Build Details Section
        details = {}
        
        global_config = shared_configs.get("global", {})
        global_params = global_config.get("parameters", {})
        
        default_language = shared_configs.get("languages", {}).get("response", {}).get("default_language")
        if not default_language:
            default_language = global_params.get("default_language", "en")
        
        details["global"] = {
            "parameters": {
                "default_language": default_language,
                "confidence_threshold": global_params.get("confidence_threshold", 0.3),
                "debug_mode": global_params.get("debug_mode", False),
                "persist_to_postgres": global_params.get("persist_to_postgres", True),
                "session_ttl_hours": global_params.get("session_ttl_hours", 24),
                "session_timeout_minutes": global_params.get("session_timeout_minutes", 30),
                "session_idle_threshold_minutes": global_params.get("session_idle_threshold_minutes", 5),
                "timeout_ms": global_params.get("timeout_ms", 5000),
                "retry_count": global_params.get("retry_count", 3)
            }
        }

        details["cache"] = {
            "parameters": {
                "backend": "redis",
                "redis_url": "${REDIS_URL:-redis://redis:6379/0}",
                "ttl_seconds": 86400,
                "max_entries": 1000
            }
        }

        for node_name, folder_name in name_to_folder.items():
            data = raw_node_configs[folder_name]
            details[node_name] = {
                "parameters": data.get("parameters", {}),
                "config": data.get("config", {})
            }

        # 4. Final Structure
        master_config = {
            "pipeline": pipeline,
            "details": details
        }
        
        # Save logic is part of the service too
        self.save_config(master_config, pipeline_config_path)
        
        return master_config

    def save_config(self, config: Dict[str, Any], path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# ============================================================\n")
            f.write("# Centralized Pipeline Configuration - AUTO-GENERATED\n")
            f.write("# ============================================================\n")
            f.write("# This file is automatically generated by PipelineConfigBuilder\n")
            f.write("# To regenerate: POST /api/v1/config/refresh or python scripts/rebuild_pipeline_config.py\n")
            f.write("# ============================================================\n\n")
            yaml.dump(config, f, sort_keys=False, allow_unicode=True, indent=2)

