import yaml
from pathlib import Path

NODES_DIR = Path("app/nodes")
SHARED_CONFIG_DIR = NODES_DIR / "_shared_config"

# Test 1: Load languages.yaml
print("=== TEST 1: Loading languages.yaml ===")
lang_file = SHARED_CONFIG_DIR / "languages.yaml"
with open(lang_file, "r", encoding="utf-8") as f:
    lang_config = yaml.safe_load(f)
    print(f"Languages config: {lang_config}")
    default_lang = lang_config.get("response", {}).get("default_language", "NOTFOUND")
    print(f"default_language extracted: {default_lang}")

# Test 2: Load query_translation config
print("\n=== TEST 2: Loading query_translation/config.yaml ===")
qt_file = NODES_DIR / "query_translation" / "config.yaml"
with open(qt_file, "r", encoding="utf-8") as f:
    qt_config = yaml.safe_load(f)
    print(f"query_translation config: {qt_config}")
    doc_lang = qt_config.get("config", {}).get("document_language", "NOTFOUND")
    print(f"document_language: {doc_lang}")

# Test 3: Simulate what rebuild script does
print("\n=== TEST 3: Simulating rebuild script logic ===")
shared_configs = {}
for config_file in SHARED_CONFIG_DIR.glob("*.yaml"):
    if config_file.name == "intents_registry.yaml":
        continue
    config_name = config_file.stem
    with open(config_file, "r", encoding="utf-8") as f:
        shared_configs[config_name] = yaml.safe_load(f) or {}

default_language = shared_configs.get("languages", {}).get("response", {}).get("default_language", "ru")
print(f"Extracted default_language: {default_language}")
print(f"All shared configs: {list(shared_configs.keys())}")
