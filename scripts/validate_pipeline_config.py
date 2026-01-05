"""
Validation script to verify rebuild_pipeline_config.py correctness
Compares source configs with generated pipeline_config.yaml
"""
import yaml
from pathlib import Path

NODES_DIR = Path("app/nodes")
SHARED_CONFIG_DIR = NODES_DIR / "_shared_config"
PIPELINE_CONFIG = Path("app/pipeline/pipeline_config.yaml")

print("=" * 80)
print("PIPELINE CONFIG VALIDATION")
print("=" * 80)

# Load generated pipeline config
with open(PIPELINE_CONFIG, "r", encoding="utf-8") as f:
    pipeline_config = yaml.safe_load(f)

errors = []
warnings = []
successes = []

# ====================
# TEST 1: Shared Configs
# ====================
print("\n1️⃣ Validating shared config integration...")
print("-" * 80)

# Load languages.yaml
with open(SHARED_CONFIG_DIR / "languages.yaml", "r", encoding="utf-8") as f:
    lang_config = yaml.safe_load(f)

expected_default_lang = lang_config.get("response", {}).get("default_language")
actual_default_lang = pipeline_config.get("details", {}).get("global", {}).get("parameters", {}).get("default_language")

if expected_default_lang == actual_default_lang:
    successes.append(f"✅ default_language: {actual_default_lang} (from languages.yaml)")
else:
    errors.append(f"❌ default_language mismatch! Expected: {expected_default_lang}, Got: {actual_default_lang}")

# ====================
# TEST 2: Node Configs
# ====================
print("\n2️⃣ Validating node configs...")
print("-" * 80)

node_count = 0
for node_dir in sorted(NODES_DIR.iterdir()):
    if not node_dir.is_dir() or node_dir.name.startswith(("_", ".")):
        continue
    
    config_file = node_dir / "config.yaml"
    if not config_file.exists():
        continue
    
    node_count += 1
    
    with open(config_file, "r", encoding="utf-8") as f:
        source_config = yaml.safe_load(f) or {}
    
    node_name = source_config.get("node", {}).get("name", node_dir.name)
    
    # Get from pipeline_config
    generated_node = pipeline_config.get("details", {}).get(node_name, {})
    
    # Compare parameters
    source_params = source_config.get("parameters", {})
    generated_params = generated_node.get("parameters", {})
    
    # Compare config
    source_conf = source_config.get("config", {})
    generated_conf = generated_node.get("config", {})
    
    if source_params == generated_params and source_conf == generated_conf:
        successes.append(f"✅ {node_name:25} - params & config match")
    else:
        if source_params != generated_params:
            errors.append(f"❌ {node_name:25} - parameters mismatch")
            print(f"   Source params: {source_params}")
            print(f"   Generated params: {generated_params}")
        if source_conf != generated_conf:
            errors.append(f"❌ {node_name:25} - config mismatch")
            print(f"   Source config keys: {list(source_conf.keys())}")
            print(f"   Generated config keys: {list(generated_conf.keys())}")

# ====================
# TEST 3: Pipeline Order
# ====================
print("\n3️⃣ Validating pipeline order...")
print("-" * 80)

pipeline_order_file = Path("app/pipeline/pipeline_order.yaml")
if pipeline_order_file.exists():
    with open(pipeline_order_file, "r", encoding="utf-8") as f:
        order_config = yaml.safe_load(f)
    expected_order = order_config.get("pipeline_order", [])
    
    actual_pipeline = pipeline_config.get("pipeline", [])
    actual_order = [node["name"] for node in actual_pipeline[:len(expected_order)]]
    
    if expected_order == actual_order:
        successes.append(f"✅ Pipeline order matches ({len(expected_order)} nodes)")
    else:
        errors.append("❌ Pipeline order mismatch!")
        print(f"   Expected: {expected_order}")
        print(f"   Actual: {actual_order}")
else:
    warnings.append("⚠️ pipeline_order.yaml not found, skipping order validation")

# ====================
# SUMMARY
# ====================
print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

print(f"\n✅ Successes: {len(successes)}")
for s in successes[:5]:  # Show first 5
    print(f"   {s}")
if len(successes) > 5:
    print(f"   ... and {len(successes) - 5} more")

if warnings:
    print(f"\n⚠️ Warnings: {len(warnings)}")
    for w in warnings:
        print(f"   {w}")

if errors:
    print(f"\n❌ Errors: {len(errors)}")
    for e in errors:
        print(f"   {e}")
    print("\n🔴 VALIDATION FAILED!")
    exit(1)
else:
    print(f"\n🟢 ALL VALIDATIONS PASSED!")
    print(f"   - Validated {node_count} node configs")
    print(f"   - Shared config integration: OK")
    print(f"   - Pipeline order: OK")
    exit(0)
