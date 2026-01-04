import time
import asyncio
from typing import Optional
from sentence_transformers import SentenceTransformer, util
from app.nodes.classification.models import ClassificationOutput
from app.nodes.classification.prompts import INTENTS, CATEGORIES

class SemanticClassificationService:
    """
    Service for Zero-Shot Classification using Semantic Embeddings (SentenceTransformers).
    """
    _instance = None
    _model = None
    _model_name = "all-MiniLM-L6-v2"  # Lightweight SOTA for semantic search
    
    # Cache for embedded labels
    _intent_embeddings = None
    _category_embeddings = None
    
    # Enrichment maps to bridge vocabulary gaps
    INTENT_MAP = {
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

    CATEGORY_MAP = {
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

    async def _ensure_model(self):
        if self._model is not None:
            return

        print(f"[SemanticClassifier] Loading semantic model {self._model_name}...", flush=True)
        try:
            loop = asyncio.get_running_loop()
            self._model = await loop.run_in_executor(None, SentenceTransformer, self._model_name)
            
            # Pre-compute embeddings for candidates
            intent_texts = [self.INTENT_MAP.get(i, i) for i in INTENTS]
            category_texts = [self.CATEGORY_MAP.get(c, c) for c in CATEGORIES]
            
            self._intent_embeddings = await loop.run_in_executor(
                None, self._model.encode, intent_texts
            )
            self._category_embeddings = await loop.run_in_executor(
                None, self._model.encode, category_texts
            )
            
            print(f"[SemanticClassifier] Model loaded and labels embedded.", flush=True)
        except Exception as e:
            print(f"[SemanticClassifier] CRITICAL ERROR loading model: {e}", flush=True)
            import traceback
            traceback.print_exc()

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

            intent, i_score = get_best(query_vec, self._intent_embeddings, INTENTS)
            category, c_score = get_best(query_vec, self._category_embeddings, CATEGORIES)

            return ClassificationOutput(
                intent=intent,
                intent_confidence=i_score,
                category=category,
                category_confidence=c_score
            )

        except Exception as e:
            print(f"[SemanticClassifier] Error: {e}", flush=True)
            return None
