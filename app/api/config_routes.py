from fastapi import APIRouter, HTTPException
from app.services.config_loader.loader import load_shared_config, clear_config_cache
from app.nodes._shared_config.history_filter import clear_filter_cache

router = APIRouter()

@router.get("/system-phrases")
async def get_system_phrases():
    """
    Get system phrases for Telegram bot.
    
    Returns filter patterns and display phrases.
    Telegram bot should call this on startup and cache the result.
    """
    try:
        config = load_shared_config("system_phrases")
        return {
            "version": config.get("version", "1.0"),
            "filter_patterns": config.get("filter_patterns", []),
            "display_phrases": config.get("display_phrases", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")


@router.get("/languages")
async def get_languages():
    """
    Get language configuration.
    
    Returns supported languages and detection settings.
    """
    try:
        config = load_shared_config("languages")
        return {
            "version": config.get("version", "1.0"),
            "detection": config.get("detection", {}),
            "response": config.get("response", {}),
            "supported": config.get("supported", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")


@router.post("/reload")
async def reload_config():
    """
    Hot-reload all cached configurations.
    
    Call this after updating YAML config files to apply changes
    without restarting the server.
    """
    try:
        from app.services.config_loader import ConfigManager
        return await ConfigManager.reload_configs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {e}")
