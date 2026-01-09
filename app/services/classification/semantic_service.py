import time
import asyncio
from typing import Optional, Dict, List
from sentence_transformers import SentenceTransformer, util
from app.nodes.classification.models import ClassificationOutput
from app.nodes._shared_config.intent_registry import get_registry, IntentRegistryService

# Fallback values if registry is empty or failed to load
FALLBACK_INTENTS = [
    "reset_password", "view_history", "contact_support", "check_policy",
    "change_address", "check_shipping_availability", "track_order",
    "check_payment_methods", "cancel_subscription", "company_info"
]

FALLBACK_CATEGORIES = [
    "Account Access", "Order Management", "Support", "Returns & Refunds",
    "Shipping", "Billing", "Account Management", "General Info"
]


class SemanticClassificationService:
    """
    Service for Zero-Shot Classification using Semantic Embeddings (SentenceTransformers).
    
    Now uses dynamic IntentRegistryService to load categories and intents from
    the auto-generated registry (built from database metadata).
    Fallback to hardcoded lists if registry is unavailable.
    """
    _instance = None
    _model = None
    _model_name = "all-MiniLM-L6-v2"  # Lightweight SOTA for semantic search
    
    # Cache for embedded labels
    _intent_embeddings = None
    _category_embeddings = None
    _current_intents: List[str] = []
    _current_categories: List[str] = []
    
    # Static enrichment maps for known labels (extends registry data)
    # These provide additional semantic context for better matching
    STATIC_INTENT_MAP = {
        "reset_password": "reset password forgot password change password сброс пароля",
        "view_history": "view order history my orders purchases история заказов",
        "contact_support": "contact support help custom service operator поддержка оператор",
        "check_policy": "return policy refund rules правила возврата",
        "change_address": "change shipping address update location изменить адрес",
        "check_shipping_availability": "shipping availability delivery countries доставка страны",
        "track_order": "track order where is my package отследить заказ",
        "check_payment_methods": "payment methods credit card paypal оплата карта",
        "cancel_subscription": "cancel subscription stop billing отменить подписку",
        "company_info": "about company contact info информация о компании"
    }

    STATIC_CATEGORY_MAP = {
        "Account Access": "account login password auth вход аккаунт",
        "Order Management": "orders history tracking status заказы статус",
        "Support": "help support questions помощь поддержка",
        "Returns & Refunds": "return money refund item возврат",
        "Shipping": "shipping delivery logistics доставка",
        "Billing": "billing payment invoice money оплата",
        "Account Management": "profile settings preferences настройки",
        "General Info": "general info about faq общее"
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SemanticClassificationService, cls).__new__(cls)
        return cls._instance

    def _get_dynamic_lists(self) -> tuple:
        """
        Get intents and categories from the dynamic registry.
        Falls back to hardcoded lists if registry is empty.
        """
        registry = get_registry()
        
        intents = registry.intents
        categories = registry.categories
        
        # Fallback if registry is empty
        if not intents:
            print("[SemanticClassifier] No intents in registry, using fallback list.", flush=True)
            intents = FALLBACK_INTENTS
        
        if not categories:
            print("[SemanticClassifier] No categories in registry, using fallback list.", flush=True)
            categories = FALLBACK_CATEGORIES
        
        return intents, categories
    
    def _build_enrichment_maps(self, intents: List[str], categories: List[str]) -> tuple:
        """
        Build enrichment maps combining static mappings with registry data.
        New labels from registry get auto-generated descriptions.
        """
        registry = get_registry()
        dynamic_intent_map, dynamic_category_map = registry.get_enrichment_maps()
        
        # Merge: static takes precedence, then dynamic, then auto-generated
        intent_map: Dict[str, str] = {}
        for intent in intents:
            if intent in self.STATIC_INTENT_MAP:
                intent_map[intent] = self.STATIC_INTENT_MAP[intent]
            elif intent in dynamic_intent_map:
                intent_map[intent] = dynamic_intent_map[intent]
            else:
                # Auto-generate from name
                intent_map[intent] = intent.replace('_', ' ').replace('-', ' ')
        
        category_map: Dict[str, str] = {}
        for category in categories:
            if category in self.STATIC_CATEGORY_MAP:
                category_map[category] = self.STATIC_CATEGORY_MAP[category]
            elif category in dynamic_category_map:
                category_map[category] = dynamic_category_map[category]
            else:
                # Auto-generate from name
                category_map[category] = category.replace('_', ' ').replace('-', ' ')
        
        return intent_map, category_map

    async def _ensure_model(self):
        if self._model is not None:
            return

        print(f"[SemanticClassifier] Loading semantic model {self._model_name}...", flush=True)
        try:
            loop = asyncio.get_running_loop()
            self._model = await loop.run_in_executor(None, SentenceTransformer, self._model_name)
            
            # Get dynamic lists from registry
            intents, categories = self._get_dynamic_lists()
            self._current_intents = intents
            self._current_categories = categories
            
            # Build enrichment maps
            intent_map, category_map = self._build_enrichment_maps(intents, categories)
            
            # Pre-compute embeddings for candidates
            intent_texts = [intent_map.get(i, i) for i in intents]
            category_texts = [category_map.get(c, c) for c in categories]
            
            self._intent_embeddings = await loop.run_in_executor(
                None, self._model.encode, intent_texts
            )
            self._category_embeddings = await loop.run_in_executor(
                None, self._model.encode, category_texts
            )
            
            print(f"[SemanticClassifier] Model loaded. Labels: {len(intents)} intents, {len(categories)} categories.", flush=True)
        except Exception as e:
            print(f"[SemanticClassifier] CRITICAL ERROR loading model: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    async def refresh_embeddings(self) -> bool:
        """
        Refresh label embeddings after registry update.
        Call this after running refresh_intents.py to pick up new categories.
        """
        if self._model is None:
            return False
        
        try:
            # Reload registry
            registry = get_registry()
            registry.reload()
            
            # Get updated lists
            intents, categories = self._get_dynamic_lists()
            self._current_intents = intents
            self._current_categories = categories
            
            # Rebuild embeddings
            intent_map, category_map = self._build_enrichment_maps(intents, categories)
            intent_texts = [intent_map.get(i, i) for i in intents]
            category_texts = [category_map.get(c, c) for c in categories]
            
            loop = asyncio.get_running_loop()
            self._intent_embeddings = await loop.run_in_executor(
                None, self._model.encode, intent_texts
            )
            self._category_embeddings = await loop.run_in_executor(
                None, self._model.encode, category_texts
            )
            
            print(f"[SemanticClassifier] Refreshed embeddings: {len(intents)} intents, {len(categories)} categories.", flush=True)
            return True
        except Exception as e:
            print(f"[SemanticClassifier] Error refreshing embeddings: {e}", flush=True)
            return False

    async def classify(self, text: str) -> Optional[ClassificationOutput]:
        try:
            await self._ensure_model()
            if self._model is None:
                return None

            start_time = time.time()
            loop = asyncio.get_running_loop()

            # Encode query
            query_vec = await loop.run_in_executor(
                None, self._model.encode, text
            )

            def get_best(query_emb, candidates_emb, original_labels):
                scores = util.cos_sim(query_emb, candidates_emb)[0]
                best_idx = scores.argmax().item()
                best_score = scores[best_idx].item()
                return original_labels[best_idx], best_score

            intent, i_score = get_best(query_vec, self._intent_embeddings, self._current_intents)
            category, c_score = get_best(query_vec, self._category_embeddings, self._current_categories)

            return ClassificationOutput(
                intent=intent,
                intent_confidence=i_score,
                category=category,
                category_confidence=c_score
            )

        except Exception as e:
            print(f"[SemanticClassifier] Error: {e}", flush=True)
            return None
