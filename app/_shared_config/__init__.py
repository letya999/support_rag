# Shared configuration directory
# Contains YAML configs shared across multiple nodes

from app._shared_config.intent_registry import (
    IntentRegistryService,
    get_registry,
    get_intents,
    get_categories
)

__all__ = [
    'IntentRegistryService',
    'get_registry',
    'get_intents',
    'get_categories'
]
