"""
Test script to verify config loading logic from rebuild_pipeline_config.py
"""
import yaml
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.services.config_loader.loader import NODES_DIR, PIPELINE_DIR, SHARED_CONFIG_DIR
except ImportError:
    ROOT_DIR = Path(__file__).parent.parent
    NODES_DIR = ROOT_DIR / "app" / "nodes"
    PIPELINE_DIR = ROOT_DIR / "app" / "pipeline"
    SHARED_CONFIG_DIR = NODES_DIR / "_shared_config"

print("=" * 80)
print("CONFIG LOADING TEST")
print("=" * 80)

# 1. Test shared configs loading
print("\n1️⃣ Testing shared configs loading from:", SHARED_CONFIG_DIR)
print("-" * 80)
shared_configs = {}
if SHARED_CONFIG_DIR.exists():
    for config_file in SHARED_CONFIG_DIR.glob("*.yaml"):
        if config_file.name == "intents_registry.yaml":
            continue
        
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_name = config_file.stem
                shared_configs[config_name] = yaml.safe_load(f) or {}
                print(f"✅ Loaded shared config: {config_name}")
                print(f"   Keys: {list(shared_configs[config_name].keys())}")
        except Exception as e:
            print(f"❌ Error reading {config_file}: {e}")

# 2. Extract default_language from languages.yaml
print("\n2️⃣ Testing default_language extraction:")
print("-" * 80)
default_language = shared_configs.get("languages", {}).get("response", {}).get("default_language", "ru")
print(f"✅ default_language = {default_language}")
print(f"   Full languages config: {shared_configs.get('languages', {})}")

# 3. Test node configs loading
print("\n3️⃣ Testing node configs loading:")
print("-" * 80)
raw_node_configs = {}
name_to_folder = {}

if NODES_DIR.exists():
    for node_dir in sorted(NODES_DIR.iterdir()):
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
                        
                        enabled = data.get("node", {}).get("enabled", True)
                        has_params = "parameters" in data
                        has_config = "config" in data
                        
                        print(f"✅ {node_name:25} | enabled={enabled} | params={has_params} | config={has_config}")
                except Exception as e:
                    print(f"❌ Error reading {config_file}: {e}")

# 4. Verify specific nodes
print("\n4️⃣ Verifying specific node configs:")
print("-" * 80)

# Check query_translation
if "query_translation" in raw_node_configs:
    qt_config = raw_node_configs["query_translation"]
    print("query_translation config:")
    print(f"  - parameters: {qt_config.get('parameters', {})}")
    print(f"  - config: {qt_config.get('config', {})}")
    doc_lang = qt_config.get("config", {}).get("document_language")
    print(f"  ✅ document_language = {doc_lang}")
else:
    print("❌ query_translation not found!")

# Check aggregation
if "aggregation" in raw_node_configs:
    agg_config = raw_node_configs["aggregation"]
    print("\naggregation config:")
    print(f"  - parameters keys: {list(agg_config.get('parameters', {}).keys())}")
    print(f"  - config keys: {list(agg_config.get('config', {}).keys())}")
else:
    print("❌ aggregation not found!")

# 5. Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"✅ Shared configs loaded: {len(shared_configs)}")
print(f"✅ Node configs loaded: {len(raw_node_configs)}")
print(f"✅ default_language: {default_language}")
print(f"✅ Nodes with config.yaml: {list(sorted(name_to_folder.keys()))[:10]}...")
