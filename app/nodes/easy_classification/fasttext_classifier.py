import os
import asyncio
import time
import urllib.request
from typing import Optional, Dict, List
import numpy as np
import fasttext
from app.nodes.classification.models import ClassificationOutput
from app.nodes.classification.prompts import INTENTS, CATEGORIES

class FastTextClassificationService:
    _instance = None
    _model = None
    _model_path = os.path.join(os.path.dirname(__file__), "models", "lid.176.ftz")
    _model_url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz" 

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FastTextClassificationService, cls).__new__(cls)
        return cls._instance

    async def _ensure_model(self):
        if self._model is not None:
            return

        if not os.path.exists(self._model_path):
            os.makedirs(os.path.dirname(self._model_path), exist_ok=True)
            print(f"[FastText] model not found. Downloading {self._model_url}...", flush=True)
            try:
                import urllib.request
                urllib.request.urlretrieve(self._model_url, self._model_path)
                print(f"[FastText] Download complete: {self._model_path}", flush=True)
            except Exception as e:
                print(f"[FastText] Failed to download model: {e}", flush=True)
                return

        if self._model is None:
            print(f"[FastText] Loading model from {self._model_path}...", flush=True)
            try:
                import fasttext
                start = time.time()
                loop = asyncio.get_running_loop()
                # Run loading in executor to not block the main loop
                self._model = await loop.run_in_executor(None, fasttext.load_model, self._model_path)
                print(f"[FastText] Model loaded in {time.time() - start:.2f}s", flush=True)
            except Exception as e:
                print(f"[FastText] CRITICAL ERROR loading model: {e}", flush=True)

    def _clean_label(self, label: str) -> str:
        return label.replace("__label__", "")

    async def classify(self, text: str) -> Optional[ClassificationOutput]:
        try:
            await self._ensure_model()
            if self._model is None:
                print("[FastText] Model is None, returning error", flush=True)
                return None

            clean_text = text.replace("\n", " ").lower()
            start_time = time.time()
            
            # Get sentence vector from query
            loop = asyncio.get_running_loop()
            query_vec = await loop.run_in_executor(
                None, 
                lambda: self._model.get_sentence_vector(clean_text)
            )
            
            # Mapping intents/categories to Russian keywords for better similarity
            intent_map = {
                "reset_password": "сброс пароля пароль",
                "view_history": "история заказов мои заказы",
                "contact_support": "поддержка помощь оператор",
                "check_policy": "правила возврата политика",
                "change_address": "изменить адрес сменить адрес",
                "check_shipping_availability": "доставка в россию международная доставка",
                "track_order": "отследить заказ где посылка",
                "check_payment_methods": "оплата способы оплаты",
                "cancel_subscription": "отменить подписку",
                "company_info": "информация о компании"
            }
            
            category_map = {
                "Account Access": "аккаунт вход пароль",
                "Order Management": "заказы история",
                "Support": "поддержка помощь",
                "Returns & Refunds": "возврат денег товара",
                "Shipping": "доставка отправка почта",
                "Billing": "оплата счета деньги",
                "Account Management": "управление аккаунтом",
                "General Info": "общая информация"
            }

            async def get_best_match(target_map, original_list):
                best_score = -1.0
                best_label = original_list[0] if original_list else "unknown"
                
                for label in original_list:
                    keyword = target_map.get(label, label)
                    label_vec = await loop.run_in_executor(
                        None,
                        lambda k=keyword: self._model.get_sentence_vector(k.lower())
                    )
                    
                    # Cosine similarity
                    norm_q = np.linalg.norm(query_vec)
                    norm_l = np.linalg.norm(label_vec)
                    if norm_q > 0 and norm_l > 0:
                        score = np.dot(query_vec, label_vec) / (norm_q * norm_l)
                    else:
                        score = 0.0
                        
                    if score > best_score:
                        best_score = score
                        best_label = label
                return best_label, float(best_score)

            intent, i_score = await get_best_match(intent_map, INTENTS)
            category, c_score = await get_best_match(category_map, CATEGORIES)
            
            duration = time.time() - start_time
            return ClassificationOutput(
                intent=intent,
                intent_confidence=i_score,
                category=category,
                category_confidence=c_score
            )
        except Exception as e:
            print(f"[FastText] Classification error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return None
