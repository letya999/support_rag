import os
import asyncio
import time
import urllib.request
from typing import Optional, Dict, List
import fasttext
from app.nodes.classification.models import ClassificationOutput
from app.nodes.classification.prompts import INTENTS, CATEGORIES

class FastTextClassificationService:
    _instance = None
    _model = None
    _model_path = os.path.join(os.path.dirname(__file__), "models", "cc.ru.300.bin")
    _model_url = "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.ru.300.bin.gz" 

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FastTextClassificationService, cls).__new__(cls)
        return cls._instance

    async def _ensure_model(self):
        if self._model is not None:
            return

        if not os.path.exists(self._model_path):
            os.makedirs(os.path.dirname(self._model_path), exist_ok=True)
            print(f"[FastText] Model file missing at {self._model_path}")
            return

        if self._model is None:
            print("[FastText] Loading model...")
            start = time.time()
            loop = asyncio.get_running_loop()
            self._model = await loop.run_in_executor(None, fasttext.load_model, self._model_path)
            print(f"[FastText] Model loaded in {time.time() - start:.2f}s")

    def _clean_label(self, label: str) -> str:
        return label.replace("__label__", "")

    async def classify(self, text: str) -> Optional[ClassificationOutput]:
        await self._ensure_model()
        if self._model is None:
            return None

        clean_text = text.replace("\n", " ")
        start_time = time.time()
        
        loop = asyncio.get_running_loop()
        labels, probs = await loop.run_in_executor(
            None, 
            lambda: self._model.predict(clean_text, k=1)
        )
        
        duration = time.time() - start_time
        raw_label = labels[0]
        confidence = probs[0]
        label = self._clean_label(raw_label)
        
        intent = "unknown"
        category = "unknown"
        
        if label in INTENTS:
            intent = label
        elif label in CATEGORIES:
            category = label
        else:
            intent = label
            
        return ClassificationOutput(
            intent=intent,
            intent_confidence=float(confidence),
            category=category,
            category_confidence=float(confidence)
        )
