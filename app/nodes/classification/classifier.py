import asyncio
from typing import Optional
from app.logging_config import logger
from transformers import pipeline
from app._shared_config.intent_registry import get_registry
from app.nodes.classification.models import ClassificationOutput

class ClassificationService:
    _instance = None
    _classifier = None
    _cache = {}
    _cache_size = 1000

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ClassificationService, cls).__new__(cls)
            # Initialize zero-shot classifier
            # Using cpu for simplicity as requested "No dependencies" implies standard env, but transformers is heavy.
            # User accepted transformers dependency.
            # Using smaller DistilBART for faster CPU performance (~2-3x faster than BART-Large)
            cls._classifier = pipeline(
                "zero-shot-classification", 
                model="valhalla/distilbart-mnli-12-1",
                device=-1 # CPU
            )
        return cls._instance

    def _get_from_cache(self, text: str) -> Optional[ClassificationOutput]:
        return self._cache.get(text)

    def _add_to_cache(self, text: str, output: ClassificationOutput):
        if len(self._cache) >= self._cache_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[text] = output

    async def classify(self, text: str) -> ClassificationOutput:
        cached = self._get_from_cache(text)
        if cached:
            return cached

        loop = asyncio.get_running_loop()
        
        import time
        start_time = time.time()
        
        # Get dynamic lists
        registry = get_registry()
        intents = registry.intents
        categories = registry.categories

        # Parallel classification
        intent_task = loop.run_in_executor(
            None, 
            lambda: self._classifier(text, intents, multi_label=False)
        )
        category_task = loop.run_in_executor(
            None, 
            lambda: self._classifier(text, categories, multi_label=False)
        )

        intent_res, category_res = await asyncio.gather(intent_task, category_task)

        duration = time.time() - start_time
        logger.debug("Classification performance", extra={"duration_s": round(duration, 3), "text_preview": text[:20]})

        output = ClassificationOutput(
            intent=intent_res['labels'][0],
            intent_confidence=intent_res['scores'][0],
            category=category_res['labels'][0],
            category_confidence=category_res['scores'][0]
        )
        
        self._add_to_cache(text, output)
        return output
