import asyncio
from typing import Optional
from transformers import pipeline
from app.nodes.classification.prompts import INTENTS, CATEGORIES
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
            cls._classifier = pipeline(
                "zero-shot-classification", 
                model="facebook/bart-large-mnli",
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
        
        # Parallel classification
        intent_task = loop.run_in_executor(
            None, 
            lambda: self._classifier(text, INTENTS, multi_label=False)
        )
        category_task = loop.run_in_executor(
            None, 
            lambda: self._classifier(text, CATEGORIES, multi_label=False)
        )

        intent_res, category_res = await asyncio.gather(intent_task, category_task)

        output = ClassificationOutput(
            intent=intent_res['labels'][0],
            intent_confidence=intent_res['scores'][0],
            category=category_res['labels'][0],
            category_confidence=category_res['scores'][0]
        )
        
        self._add_to_cache(text, output)
        return output
