"""
Intent Registry Service - Singleton service for loading and accessing intents registry.

This service provides runtime access to the dynamic categories and intents structure,
fetched directly from the database (documents metadata).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import psycopg

from app.settings import settings

logger = logging.getLogger(__name__)

class IntentRegistryService:
    """
    Singleton service for managing the intent registry.
    
    Provides:
    - Loading/reloading of the registry from Database
    - Access to categories and intents lists
    - Enrichment maps for semantic classification
    - In-memory caching of the structure
    """
    
    _instance: Optional['IntentRegistryService'] = None
    _initialized: bool = False
    
    # Cached data
    _categories: List[str] = []
    _intents: List[str] = []
    _category_to_intents: Dict[str, List[str]] = {}
    _intent_to_category: Dict[str, str] = {}
    _category_descriptions: Dict[str, str] = {}
    _last_loaded_at: Optional[datetime] = None
    _loading_lock = asyncio.Lock()
    
    def __new__(cls) -> 'IntentRegistryService':
        if cls._instance is None:
            cls._instance = super(IntentRegistryService, cls).__new__(cls)
        return cls._instance
    
    @property
    def is_loaded(self) -> bool:
        """Check if registry is loaded."""
        return self._last_loaded_at is not None
    
    async def initialize(self) -> bool:
        """Async initialization."""
        async with self._loading_lock:
            return await self._load_registry_from_db()

    async def reload(self) -> bool:
        """Force reload the registry from DB."""
        async with self._loading_lock:
            return await self._load_registry_from_db()
            
    async def _load_registry_from_db(self) -> bool:
        """
        Fetch unique categories and their associated intents from the documents table
        and build the in-memory registry.
        """
        if not settings.DATABASE_URL:
            logger.error("DATABASE_URL not set, cannot load registry.")
            return False

        try:
            # 1. Fetch Structure
            categories_intents: Dict[str, List[str]] = {}
            
            async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT 
                            COALESCE(metadata->>'category', 'unknown') as category,
                            COALESCE(metadata->>'intent', 'unknown') as intent
                        FROM documents
                        WHERE metadata->>'category' IS NOT NULL
                        GROUP BY metadata->>'category', metadata->>'intent'
                    """)
                    
                    rows = await cur.fetchall()
                    for cat, intent in rows:
                        if not cat: continue
                        if cat not in categories_intents:
                            categories_intents[cat] = []
                        
                        if intent and intent != 'unknown' and intent not in categories_intents[cat]:
                            categories_intents[cat].append(intent)

            # 2. Build Internal Structures
            new_categories = []
            new_intents = []
            new_cat_to_intents = {}
            new_intent_to_cat = {}
            new_descriptions = {}

            for cat, intents in sorted(categories_intents.items()):
                new_categories.append(cat)
                sorted_intents = sorted(intents)
                new_cat_to_intents[cat] = sorted_intents
                
                # Generate Description
                new_descriptions[cat] = self._generate_description(cat, sorted_intents)
                
                for intent in sorted_intents:
                    if intent not in new_intents:
                        new_intents.append(intent)
                    new_intent_to_cat[intent] = cat

            # 3. Apply Update
            self._categories = new_categories
            self._intents = new_intents
            self._category_to_intents = new_cat_to_intents
            self._intent_to_category = new_intent_to_cat
            self._category_descriptions = new_descriptions
            self._last_loaded_at = datetime.now(timezone.utc)
            
            logger.info(f"[IntentRegistry] Loaded from DB: {len(self._categories)} categories, {len(self._intents)} intents")
            return True

        except Exception as e:
            logger.error(f"[IntentRegistry] Error loading from DB: {e}")
            return False

    def _generate_description(self, category: str, intents: List[str]) -> str:
        """Generate description locally (same logic as old RegistryGenerator)."""
        readable_name = category.replace("_", " ").replace("-", " ").title()
        description = f"Questions related to {readable_name}"
        
        if intents:
            top_intents = [
                i.replace("_", " ").replace("-", " ").lower() 
                for i in intents[:3] # Limit to 3 for brevity in description
            ]
            if top_intents:
                description += f", including {', '.join(top_intents)}"
                if len(intents) > 3:
                    description += ", and others"
        
        return description + "."

    # --- Synchronous Accessors (Assumption: Data is loaded) ---
    # These method calls assume initialize() has been called during app startup.
    # If not loaded, they return empty/None gracefully or could raise error.
    
    @property
    def categories(self) -> List[str]:
        return self._categories.copy()
    
    @property
    def intents(self) -> List[str]:
        return self._intents.copy()
    
    def get_intents_for_category(self, category: str) -> List[str]:
        return self._category_to_intents.get(category, []).copy()
    
    def get_category_for_intent(self, intent: str) -> Optional[str]:
        return self._intent_to_category.get(intent)
    
    def get_category_description(self, category: str) -> Optional[str]:
        return self._category_descriptions.get(category)
    
    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "generated_at": str(self._last_loaded_at),
            "source_db": "postgres:documents",
            "total_categories": len(self._categories),
            "total_intents": len(self._intents)
        }

    def get_enrichment_maps(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Generate enrichment maps from in-memory data."""
        intent_map: Dict[str, str] = {}
        category_map: Dict[str, str] = {}
        
        for cat, desc in self._category_descriptions.items():
            category_map[cat] = f"{cat} {desc}"
        
        for intent in self._intents:
            readable = intent.replace('_', ' ').replace('-', ' ')
            intent_map[intent] = readable
            
        return intent_map, category_map


def get_registry() -> IntentRegistryService:
    return IntentRegistryService()

# Backward compatibility functions
def get_intents() -> List[str]:
    return get_registry().intents

def get_categories() -> List[str]:
    return get_registry().categories
