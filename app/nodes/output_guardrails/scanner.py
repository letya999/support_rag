"""
Output Guardrails Scanner Service

Validates LLM responses for:
- Data leakage (PII, credentials)
- Toxicity
- Relevance to user query
- Hallucination indicators
"""
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class OutputScanResult:
    """Result of output security scan"""
    is_safe: bool
    risk_score: float  # 0.0 - 1.0
    triggered_scanners: List[str]
    sanitized_text: Optional[str] = None
    details: Dict = None


class DataLeakageScanner:
    """Detect PII and sensitive data in responses"""
    
    def __init__(self, patterns: List[Dict]):
        self.patterns = [
            {
                "regex": re.compile(p["pattern"], re.MULTILINE),
                "description": p["description"]
            }
            for p in patterns
        ]
    
    def scan(self, text: str) -> Tuple[bool, float, List[str], Optional[str]]:
        """
        Returns: (is_safe, risk_score, triggered_patterns, sanitized_text)
        """
        triggered = []
        sanitized = text
        
        for pattern in self.patterns:
            matches = pattern["regex"].findall(text)
            if matches:
                triggered.append(pattern["description"])
                # Sanitize: replace with [REDACTED]
                sanitized = pattern["regex"].sub("[УДАЛЕНО]", sanitized)
        
        is_safe = len(triggered) == 0
        risk_score = min(1.0, len(triggered) * 0.4)
        
        return is_safe, risk_score, triggered, sanitized if not is_safe else None
    

class RelevanceScanner:
    """Check if response is relevant to user query"""
    
    # Common off-topic phrases
    OFF_TOPIC_PHRASES = [
        "я не могу помочь с этим",
        "это не входит в мои обязанности",
        "это за пределами моих возможностей",
        "обратитесь к другому специалисту",
        "I cannot help with that",
        "this is outside my scope",
        "contact another specialist"
    ]
    
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.off_topic_patterns = [
            re.compile(phrase, re.IGNORECASE)
            for phrase in self.OFF_TOPIC_PHRASES
        ]
    
    def scan(self, response: str, user_query: str) -> Tuple[bool, float]:
        """
        Simple heuristic check for relevance.
        More advanced version would use semantic similarity.
        """
        # Check for off-topic phrases
        for pattern in self.off_topic_patterns:
            if pattern.search(response):
                return False, 0.8  # High risk, likely off-topic refusal
        
        # Check if response is too short (likely unhelpful)
        if len(response.strip()) < 20:
            return False, 0.3
        
        # Passed basic checks
        return True, 0.0


class HallucinationScanner:
    """Detect potential hallucinations"""
    
    def __init__(self, indicators: List[str], threshold: float = 0.6):
        self.indicators = indicators
        self.threshold = threshold
    
    def scan(self, response: str) -> Tuple[bool, float, List[str]]:
        """
        Detect uncertainty keywords that may indicate hallucination.
        """
        found_indicators = []
        response_lower = response.lower()
        
        for indicator in self.indicators:
            if indicator.lower() in response_lower:
                found_indicators.append(indicator)
        
        # Calculate risk based on number of indicators
        risk_score = min(1.0, len(found_indicators) * 0.2)
        is_safe = risk_score < self.threshold
        
        return is_safe, risk_score, found_indicators


class RefusalDetectionScanner:
    """Detect when model refuses to answer valid requests"""
    
    REFUSAL_PATTERNS = [
        r"(?i)я не могу.*ответить",
        r"(?i)извините.*не могу помочь",
        r"(?i)I cannot.*answer",
        r"(?i)I'm sorry.*I can't help"
    ]
    
    def __init__(self):
        self.patterns = [re.compile(p) for p in self.REFUSAL_PATTERNS]
    
    def scan(self, response: str) -> Tuple[bool, float]:
        """
        Returns (has_refusal, confidence)
        This is inverted: refusal = not safe for "no_refusal" scanner
        """
        for pattern in self.patterns:
            if pattern.search(response):
                return True, 0.8  # High confidence refusal detected
        
        return False, 0.0


class BasicOutputGuardrailsService:
    """
    Basic output validation using regex and heuristics.
    """
    
    def __init__(
        self,
        data_leakage_patterns: List[Dict],
        hallucination_indicators: List[str],
        relevance_threshold: float = 0.5,
        hallucination_threshold: float = 0.6
    ):
        self.data_leakage_scanner = DataLeakageScanner(data_leakage_patterns)
        self.relevance_scanner = RelevanceScanner(relevance_threshold)
        self.hallucination_scanner = HallucinationScanner(
            hallucination_indicators,
            hallucination_threshold
        )
        self.refusal_scanner = RefusalDetectionScanner()
    
    async def scan(
        self,
        response: str,
        user_query: str,
        enabled_scanners: Dict[str, bool] = None
    ) -> OutputScanResult:
        """
        Scan LLM output for security issues.
        """
        if enabled_scanners is None:
            enabled_scanners = {
                "data_leakage": True,
                "relevance": True,
                "hallucination": False,
                "refusal_detection": False
            }
        
        triggered = []
        max_risk = 0.0
        details = {}
        sanitized_text = None
        
        # 1. Data leakage
        if enabled_scanners.get("data_leakage", True):
            is_safe, risk, patterns, sanitized = self.data_leakage_scanner.scan(response)
            if not is_safe:
                triggered.append("data_leakage")
                details["data_leakage"] = patterns
                sanitized_text = sanitized
            max_risk = max(max_risk, risk)
        
        # 2. Relevance
        if enabled_scanners.get("relevance", True):
            is_safe, risk = self.relevance_scanner.scan(response, user_query)
            if not is_safe:
                triggered.append("relevance")
                details["relevance"] = "Response appears off-topic or unhelpful"
            max_risk = max(max_risk, risk)
        
        # 3. Hallucination
        if enabled_scanners.get("hallucination", False):
            is_safe, risk, indicators = self.hallucination_scanner.scan(response)
            if not is_safe:
                triggered.append("hallucination")
                details["hallucination"] = indicators
            max_risk = max(max_risk, risk)
        
        # 4. Refusal detection
        if enabled_scanners.get("refusal_detection", False):
            has_refusal, risk = self.refusal_scanner.scan(response)
            if has_refusal:
                triggered.append("refusal")
                details["refusal"] = "Model refused to answer"
            max_risk = max(max_risk, risk)
        
        return OutputScanResult(
            is_safe=len(triggered) == 0,
            risk_score=max_risk,
            triggered_scanners=triggered,
            sanitized_text=sanitized_text,
            details=details
        )


# Singleton instance
_output_service: Optional[BasicOutputGuardrailsService] = None


def get_output_guardrails_service(
    data_leakage_patterns: List[Dict],
    hallucination_indicators: List[str],
    relevance_threshold: float = 0.5,
    hallucination_threshold: float = 0.6
) -> BasicOutputGuardrailsService:
    """Get or create singleton instance"""
    global _output_service
    if _output_service is None:
        _output_service = BasicOutputGuardrailsService(
            data_leakage_patterns=data_leakage_patterns,
            hallucination_indicators=hallucination_indicators,
            relevance_threshold=relevance_threshold,
            hallucination_threshold=hallucination_threshold
        )
    return _output_service
