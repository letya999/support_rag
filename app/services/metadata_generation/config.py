"""
Configuration loader for metadata generation service.
"""

import os
import yaml
from typing import Dict, Any, Optional
from .models import MetadataConfig


# Default configuration path
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "..",
    "config",
    "metadata_generation.yaml"
)


def load_config(config_path: Optional[str] = None) -> MetadataConfig:
    """
    Load metadata generation configuration from YAML file.

    Args:
        config_path: Path to config file (uses default if None)

    Returns:
        MetadataConfig instance
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    if not os.path.exists(config_path):
        print(f"[Config] Config file not found at {config_path}, using defaults")
        return MetadataConfig()

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            return MetadataConfig()

        # Extract metadata_generation section
        mg_config = config_data.get('metadata_generation', {})

        # Build config kwargs
        config_kwargs = {
            'confidence_threshold_high': mg_config.get(
                'confidence_threshold_high',
                0.75
            ),
            'confidence_threshold_low': mg_config.get(
                'confidence_threshold_low',
                0.70
            ),
            'context_examples_count': mg_config.get(
                'context_examples_count',
                3
            ),
            'context_chunks_count': mg_config.get(
                'context_chunks_count',
                3
            ),
            'chunk_preview_length': mg_config.get(
                'chunk_preview_length',
                150
            ),
            'llm_batch_size': mg_config.get(
                'llm_batch_size',
                20
            ),
            'max_parallel_batches': mg_config.get(
                'max_parallel_batches',
                5
            ),
        }

        config = MetadataConfig(**config_kwargs)
        print(f"[Config] Loaded configuration from {config_path}")

        return config

    except Exception as e:
        print(f"[Config] Error loading config from {config_path}: {e}")
        return MetadataConfig()


# Global config instance
_config_instance: Optional[MetadataConfig] = None


def get_config() -> MetadataConfig:
    """Get the global metadata generation configuration instance."""
    global _config_instance

    if _config_instance is None:
        _config_instance = load_config()

    return _config_instance


def reload_config(config_path: Optional[str] = None) -> MetadataConfig:
    """Reload configuration from file."""
    global _config_instance
    _config_instance = load_config(config_path)
    return _config_instance
