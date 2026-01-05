import yaml
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.services.config_loader.loader import NODES_DIR, PIPELINE_DIR, SHARED_CONFIG_DIR
except ImportError:
    # Fallback if executed from wrong directory or before app is fully structured
    ROOT_DIR = Path(__file__).parent.parent
    NODES_DIR = ROOT_DIR / "app" / "nodes"
    PIPELINE_DIR = ROOT_DIR / "app" / "pipeline"
    SHARED_CONFIG_DIR = NODES_DIR / "_shared_config"


def load_pipeline_order():
    """Load pipeline order from YAML config file."""
    order_file = PIPELINE_DIR / "pipeline_order.yaml"
    if not order_file.exists():
        print(f"⚠️ Warning: {order_file} not found. Using default order.")
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


def load_shared_configs():
    """Load all shared configs from _shared_config directory."""
    shared_configs = {}
    if not SHARED_CONFIG_DIR.exists():
        return shared_configs
    
    for config_file in SHARED_CONFIG_DIR.glob("*.yaml"):
        if config_file.name == "intents_registry.yaml":
            # Skip the auto-generated intents registry
            continue
        
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_name = config_file.stem
                shared_configs[config_name] = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"⚠️ Error reading shared config {config_file}: {e}")
    
    return shared_configs


def generate_full_config():
    pipeline_config_path = PIPELINE_DIR / "pipeline_config.yaml"
    
    # 0. Load pipeline order from config
    PIPELINE_ORDER = load_pipeline_order()
    print(f"📋 Using pipeline order from: app/pipeline/pipeline_order.yaml")
    
    # 0.1. Load shared configs
    shared_configs = load_shared_configs()
    if shared_configs:
        print(f"📚 Loaded {len(shared_configs)} shared configs: {', '.join(shared_configs.keys())}")
    
    # 1. Collect all node configs from app/nodes/
    # Map: FolderName -> ConfigData
    raw_node_configs = {}
    # Map: NodeName (from yaml) -> FolderName
    name_to_folder = {}
    
    if not NODES_DIR.exists():
        print(f"❌ Error: NODES_DIR {NODES_DIR} not found.")
        return

    for node_dir in NODES_DIR.iterdir():
        if node_dir.is_dir() and not node_dir.name.startswith(("_", ".")):
            config_file = node_dir / "config.yaml"
            if config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                        raw_node_configs[node_dir.name] = data
                        
                        # Use internal name if provided, else folder name
                        node_name = data.get("node", {}).get("name", node_dir.name)
                        name_to_folder[node_name] = node_dir.name
                except Exception as e:
                    print(f"⚠️ Error reading {config_file}: {e}")

    # 2. Build Pipeline Section
    pipeline = []
    processed_nodes = set()
    
    for node_name in PIPELINE_ORDER:
        enabled = False
        
        # Check if we have a folder for this node name (or mapped name)
        folder_name = name_to_folder.get(node_name, node_name)
        
        if folder_name in raw_node_configs:
            enabled = raw_node_configs[folder_name].get("node", {}).get("enabled", True)
            processed_nodes.add(node_name)
        elif node_name in ["check_cache", "store_in_cache"]:
            # Special nodes managed by the graph but using global cache settings
            enabled = True
            processed_nodes.add(node_name)
        else:
            # If it's in PIPELINE_ORDER but not found, keep it as disabled placeholder
            # to let the user know it's a known pipeline stage
            enabled = False
        
        pipeline.append({
            "name": node_name,
            "enabled": enabled
        })

    # Add any extra nodes found in folders but not in PIPELINE_ORDER
    for node_name, folder_name in sorted(name_to_folder.items()):
        if node_name not in processed_nodes:
            pipeline.append({
                "name": node_name,
                "enabled": raw_node_configs[folder_name].get("node", {}).get("enabled", True)
            })

    # 3. Build Details Section
    details = {}
    
    # Global Parameters (Defaults)
    details["global"] = {
        "parameters": {
            "default_language": "ru",
            "confidence_threshold": 0.3,
            "debug_mode": False,
            "persist_to_postgres": True,
            "session_ttl_hours": 24,
            "session_timeout_minutes": 30,
            "session_idle_threshold_minutes": 5,
            "timeout_ms": 5000,
            "retry_count": 3
        }
    }
    
    # Cache Configuration (Defaults)
    details["cache"] = {
        "parameters": {
            "backend": "redis",
            "redis_url": "${REDIS_URL:-redis://redis:6379/0}",
            "ttl_seconds": 86400,
            "max_entries": 1000
        }
    }

    # Map raw node details into the centralized config
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

    # 5. Save with Header
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    with open(pipeline_config_path, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# Centralized Pipeline Configuration - AUTO-GENERATED\n")
        f.write("# ============================================================\n")
        f.write("# This file is automatically generated from:\n")
        f.write("# - app/nodes/*/config.yaml (node-specific configs)\n")
        f.write("# - app/nodes/_shared_config/*.yaml (shared configs)\n")
        f.write("# - app/pipeline/pipeline_order.yaml (pipeline sequence)\n")
        f.write("#\n")
        f.write("# Rules:\n")
        f.write("# 1. Node name is taken from node.name in local config.yaml (or folder name).\n")
        f.write("# 2. Numeric/Boolean params go to 'parameters', rest go to 'config'.\n")
        f.write("# 3. The 'pipeline' section order is defined in pipeline_order.yaml.\n")
        f.write("#\n")
        f.write("# To regenerate: python scripts/rebuild_pipeline_config.py\n")
        f.write("# ============================================================\n\n")
        yaml.dump(master_config, f, sort_keys=False, allow_unicode=True, indent=2)

    print(f"✅ Rebuilt {pipeline_config_path}")
    print(f"📦 Included {len(raw_node_configs)} nodes from app/nodes folders")
    print(f"🔗 Pipeline contains {len(pipeline)} nodes total")

if __name__ == "__main__":
    generate_full_config()
