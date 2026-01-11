"""
Intent Registry Service - Singleton service for loading and accessing intents registry.

This service provides runtime access to the auto-generated intents_registry.yaml file,
allowing the classification system to work with dynamic categories and intents.
"""

import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import yaml


# Path to the registry file
REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "intents_registry.yaml"
)


class IntentRegistryService:
    """
    Singleton service for managing the intent registry.
    
    Provides:
    - Loading/reloading of the registry from YAML
    - Access to categories and intents lists
    - Enrichment maps for semantic classification
    - Validation of categories/intents
    """
    
    _instance: Optional['IntentRegistryService'] = None
    _initialized: bool = False
    
    # Cached data
    _registry_data: Dict[str, Any] = {}
    _categories: List[str] = []
    _intents: List[str] = []
    _category_to_intents: Dict[str, List[str]] = {}
    _intent_to_category: Dict[str, str] = {}
    _last_loaded_at: Optional[datetime] = None
    
    def __new__(cls) -> 'IntentRegistryService':
        if cls._instance is None:
            cls._instance = super(IntentRegistryService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if not IntentRegistryService._initialized:
            self._load_registry()
            IntentRegistryService._initialized = True
    
    def _load_registry(self, force: bool = False) -> bool:
        """
        Load or reload the registry from YAML file.
        
        Args:
            force: Force reload even if already loaded
            
        Returns:
            True if loaded successfully, False otherwise
        """
        if self._last_loaded_at is not None and not force:
            return True
        
        if not os.path.exists(REGISTRY_PATH):
            print(f"[IntentRegistry] Warning: Registry file not found at {REGISTRY_PATH}")
            print("[IntentRegistry] Using fallback empty registry. Run 'python scripts/refresh_intents.py' to generate.")
            self._categories = []
            self._intents = []
            self._category_to_intents = {}
            self._intent_to_category = {}
            self._last_loaded_at = datetime.now()
            return False
        
        try:
            with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
                self._registry_data = yaml.safe_load(f) or {}
            
            # Parse categories
            self._categories = []
            self._intents = []
            self._category_to_intents = {}
            self._intent_to_category = {}
            
            categories_list = self._registry_data.get('categories', [])
            
            for cat_entry in categories_list:
                cat_name = cat_entry.get('name', '')
                if not cat_name:
                    continue
                    
                self._categories.append(cat_name)
                cat_intents = cat_entry.get('intents', [])
                self._category_to_intents[cat_name] = cat_intents
                
                for intent in cat_intents:
                    if intent not in self._intents:
                        self._intents.append(intent)
                    self._intent_to_category[intent] = cat_name
            
            self._last_loaded_at = datetime.now()
            
            print(f"[IntentRegistry] Loaded registry: {len(self._categories)} categories, {len(self._intents)} intents")
            return True
            
        except Exception as e:
            print(f"[IntentRegistry] Error loading registry: {e}")
            return False
    
    def reload(self) -> bool:
        """Force reload the registry from file."""
        return self._load_registry(force=True)
    
    @property
    def categories(self) -> List[str]:
        """Get list of all categories."""
        return self._categories.copy()
    
    @property
    def intents(self) -> List[str]:
        """Get list of all unique intents."""
        return self._intents.copy()
    
    def get_intents_for_category(self, category: str) -> List[str]:
        """Get list of intents that belong to a specific category."""
        return self._category_to_intents.get(category, []).copy()
    
    def get_category_for_intent(self, intent: str) -> Optional[str]:
        """Get the category that an intent belongs to."""
        return self._intent_to_category.get(intent)
    
    def is_valid_category(self, category: str) -> bool:
        """Check if a category exists in the registry."""
        return category in self._categories
    
    def is_valid_intent(self, intent: str) -> bool:
        """Check if an intent exists in the registry."""
        return intent in self._intents
    
    def is_valid_intent_for_category(self, intent: str, category: str) -> bool:
        """Check if an intent is valid for a given category."""
        return intent in self._category_to_intents.get(category, [])
    
    def get_category_description(self, category: str) -> Optional[str]:
        """Get the description for a category."""
        for cat_entry in self._registry_data.get('categories', []):
            if cat_entry.get('name') == category:
                return cat_entry.get('description')
        return None
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Get registry metadata (generation time, source, etc.)."""
        return self._registry_data.get('_meta', {}).copy()
    
    @property
    def is_loaded(self) -> bool:
        """Check if registry is loaded."""
        return self._last_loaded_at is not None
    
    @property
    def last_loaded_at(self) -> Optional[datetime]:
        """Get when the registry was last loaded."""
        return self._last_loaded_at
    
    def get_enrichment_maps(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Generate enrichment maps for semantic classification.
        
        Returns:
            Tuple of (intent_map, category_map) where each map contains
            the label name mapped to an enriched text for embedding.
        """
        intent_map: Dict[str, str] = {}
        category_map: Dict[str, str] = {}
        
        # Build category map with descriptions
        for cat_entry in self._registry_data.get('categories', []):
            cat_name = cat_entry.get('name', '')
            cat_desc = cat_entry.get('description', cat_name)
            if cat_name:
                # Combine name and description for better semantic matching
                category_map[cat_name] = f"{cat_name} {cat_desc}"
        
        # Build intent map (for now, just use readable versions of intent names)
        for intent in self._intents:
            # Convert snake_case to readable text
            readable = intent.replace('_', ' ').replace('-', ' ')
            intent_map[intent] = readable
        
        return intent_map, category_map


# Convenience function for quick access
def get_registry() -> IntentRegistryService:
    """Get the singleton IntentRegistryService instance."""
    return IntentRegistryService()


# Export lists for backward compatibility with prompts.py style imports
def get_intents() -> List[str]:
    """Get list of all intents (backward compatibility)."""
    return get_registry().intents


def get_categories() -> List[str]:
    """Get list of all categories (backward compatibility)."""
    return get_registry().categories
