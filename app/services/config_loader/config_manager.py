"""
Centralized configuration management.
Handles reloading of all system configurations and caches.
"""
from app.services.config_loader.loader import clear_config_cache
from app.nodes._shared_config.history_filter import clear_filter_cache

class ConfigManager:
    @staticmethod
    async def clear_all_caches() -> dict:
        """Clear all configuration caches"""
        clear_config_cache()
        clear_filter_cache()
        return {"status": "ok", "message": "All caches cleared"}
    
    @staticmethod
    async def reload_configs() -> dict:
        """Reload all configurations"""
        return await ConfigManager.clear_all_caches()
