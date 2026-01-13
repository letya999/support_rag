# Configuration Guide

Support RAG uses a hierarchical configuration system that combines environment variables with YAML files.

## 🛠️ Configuration Layers

1.  **Environment Variables (`.env`)**: Infrastructure settings (DB URLs, API keys).
2.  **Shared Config (`app/_shared_config/`)**: Domain-agnostic pipeline parameters.
3.  **Node Configs (`app/nodes/*/config.yaml`)**: Settings specific to a single processing node.

## 🌍 Global Configuration (`global.yaml`)

Defined in `app/_shared_config/global.yaml`.

- **`default_language`**: The fallback language for translation and generation.
- **`confidence_threshold`**: Answers with confidence below this value will trigger escalation.
- **`session_ttl_hours`**: How long a session stays active in Redis.
- **`timeout_ms`**: Global timeout for node execution.

## ⚡ Cache Configuration (`cache.yaml`)

Defined in `app/_shared_config/cache.yaml`.

- **`redis_url`**: Connection string.
- **`max_entries`**: Maximum number of items in the semantic cache.
- **`similarity_threshold`**: Minimum similarity (0.0 - 1.0) to consider a cache hit.
- **`ttl_seconds`**: Expiration for cache entries.

## 🏷️ Intent Registry

The system uses a dynamic taxonomy of **Categories** and **Intents**. These can be managed via the Database, but initial seeds or overrides may exist in `app/_shared_config/intent_registry.py`.

## 💬 System Phrases (`system_phrases.yaml`)

This file contains multi-lingual strings for the bot's static responses:
- Greetings.
- Escalation messages.
- Error notifications.
- Clarification prompts.

## 🛠️ How to Modify Configuration

### 1. Simple Values
Update the `.env` file for API keys or ports. Restart the application for changes to take effect.

### 2. Pipeline Behavior
Modify the YAML files in `app/_shared_config/`. Many of these values are reloaded periodically or on every request (depending on the node implementation).

### 3. Adding New Settings
To add a new configuration setting:
1.  Add it to the relevant YAML file.
2.  In your Python code, use the `ConfigLoader`:
    ```python
    from app.services.config_loader.loader import load_shared_config
    
    cfg = load_shared_config("global")
    threshold = cfg.get("parameters", {}).get("new_setting", 0.5)
    ```
