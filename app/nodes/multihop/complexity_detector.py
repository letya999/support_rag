import re
from typing import List, Literal, Dict
from .models import ComplexityOutput

MARKERS = {
    "question_words": {
        "en": ["how", "why", "what", "when", "which", "where", "explain", "describe"],
        "ru": ["как", "почему", "зачем", "что", "когда", "какой", "где", "объясни", "опиши"]
    },
    "logical_connectors": {
        "en": ["if", "then", "else", "because", "unless", "provided", "assuming", "after", "before"],
        "ru": ["если", "то", "иначе", "потому", "так как", "хотя", "при условии", "после", "до"]
    },
    "conjunctions": {
        "en": ["and", "or", "also", "with", "besides"],
        "ru": ["и", "или", "также", "с", "кроме"]
    }
}

class ComplexityDetector:
    def __init__(self):
        pass

    def detect_language(self, text: str) -> Literal["ru", "en"]:
        # Simple heuristic: if contains cyrillic, it's RU
        if re.search(r'[а-яА-ЯёЁ]', text):
            return "ru"
        return "en"

    def detect(self, text: str) -> ComplexityOutput:
        text_lower = text.lower()
        lang = self.detect_language(text)
        
        detected_markers = []
        score = 0.0
        
        # Word counts for scoring
        words = re.findall(r'\w+', text_lower)
        word_count = len(words)
        
        # 1. Question words
        for word in MARKERS["question_words"][lang]:
            if word in words:
                score += 1.0
                detected_markers.append(word)
        
        # 2. Logical connectors
        for connector in MARKERS["logical_connectors"][lang]:
            # Use regex for multi-word connectors like "так как" or "при условии"
            if re.search(r'\b' + re.escape(connector) + r'\b', text_lower):
                score += 1.5
                detected_markers.append(connector)
                
        # 3. Conjunctions
        for conj in MARKERS["conjunctions"][lang]:
            if conj in words:
                score += 0.5
                detected_markers.append(conj)
                
        # 4. Structural analysis
        commas = text.count(',')
        score += commas * 0.5
        
        if word_count > 25:
            score += 2.0
        elif word_count > 15:
            score += 1.0
            
        # Mapping score to level and hops
        if score < 1.5:
            level = "simple"
            num_hops = 1
        elif score < 3.5:
            level = "medium"
            num_hops = 2
        else:
            level = "complex"
            num_hops = 3
            
        # Confidence calculation (very basic placeholder)
        confidence = min(1.0, 0.5 + (len(detected_markers) * 0.1))
        
        return ComplexityOutput(
            complexity_level=level,
            complexity_score=score,
            language=lang,
            detected_markers=detected_markers,
            num_hops=num_hops,
            confidence=confidence
        )
