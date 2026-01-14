import torch
from transformers import MarianMTModel, MarianTokenizer
from langdetect import detect, DetectorFactory
from typing import Optional
from app.logging_config import logger

# Ensure consistent results from langdetect
DetectorFactory.seed = 0

class QueryTranslator:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer_ru_en = None
        self.model_ru_en = None
        self.tokenizer_en_ru = None
        self.model_en_ru = None
        logger.info("QueryTranslator initialized", extra={"device": self.device})

    def _load_ru_en(self):
        if self.model_ru_en is None:
            model_name = "Helsinki-NLP/opus-mt-ru-en"
            logger.info("Loading translation model", extra={"model": model_name})
            self.tokenizer_ru_en = MarianTokenizer.from_pretrained(model_name)
            self.model_ru_en = MarianMTModel.from_pretrained(model_name).to(self.device)

    def _load_en_ru(self):
        if self.model_en_ru is None:
            model_name = "Helsinki-NLP/opus-mt-en-ru"
            logger.info("Loading translation model", extra={"model": model_name})
            self.tokenizer_en_ru = MarianTokenizer.from_pretrained(model_name)
            self.model_en_ru = MarianMTModel.from_pretrained(model_name).to(self.device)

    def translate_ru_to_en(self, text: str) -> str:
        self._load_ru_en()
        self.model_ru_en.eval()
        with torch.no_grad():
            inputs = self.tokenizer_ru_en(text, return_tensors="pt", padding=True).to(self.device)
            translated = self.model_ru_en.generate(**inputs)
            return self.tokenizer_ru_en.decode(translated[0], skip_special_tokens=True)

    def translate_en_to_ru(self, text: str) -> str:
        self._load_en_ru()
        self.model_en_ru.eval()
        with torch.no_grad():
            inputs = self.tokenizer_en_ru(text, return_tensors="pt", padding=True).to(self.device)
            translated = self.model_en_ru.generate(**inputs)
            return self.tokenizer_en_ru.decode(translated[0], skip_special_tokens=True)

    def detect_language(self, text: str) -> str:
        try:
            return detect(text)
        except:
            return "en"

    def translate_query(self, query: str, target_lang: str = "en") -> str:
        """
        Translates query to target language if it's different.
        """
        current_lang = self.detect_language(query)
        
        # Normalize cyrillic slavic languages to Russian
        # Our translation models only support ru-en, so we treat all cyrillic 
        # slavic languages (Bulgarian, Ukrainian, Belarusian, Macedonian, Serbian) 
        # as Russian for translation purposes
        cyrillic_slavic_langs = {'bg', 'uk', 'be', 'mk', 'sr'}
        
        if current_lang in cyrillic_slavic_langs:
            logger.info(
                f"Detected {current_lang}, treating as Russian for translation", 
                extra={"query": query, "original_lang": current_lang}
            )
            current_lang = "ru"
        
        # Handle cases where language codes might differ slightly (e.g. "ru" vs "ru-RU")
        # For this simple implementation, we assume simple 2-letter codes.
        
        if current_lang == target_lang:
            return query
        
        if current_lang == "ru" and target_lang == "en":
            return self.translate_ru_to_en(query)
        elif current_lang == "en" and target_lang == "ru":
            return self.translate_en_to_ru(query)
            
        return query

    def warmup(self):
        """Preload models into memory."""
        logger.info("Warming up translator models")
        self._load_ru_en()
        self._load_en_ru()
        logger.info("Translator models loaded")

translator = QueryTranslator.get_instance()
