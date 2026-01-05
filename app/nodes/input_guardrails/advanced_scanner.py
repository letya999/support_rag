"""
Advanced Guardrails Service using LLM Guard

This module provides ML-based protection using the LLM Guard library.
It's optional and requires: pip install llm-guard

Features:
- ML-based prompt injection detection
- Toxicity detection with transformer models
- Semantic topic banning
- PII detection
- Jailbreak detection

Note: This is heavier than basic guardrails (~50-200ms latency)
"""
from typing import List, Dict, Optional
from dataclasses import dataclass
import asyncio

try:
    from llm_guard.input_scanners import (
        PromptInjection,
        Toxicity,
        BanTopics,
        Secrets,
        Language as LLMGuardLanguage,
        TokenLimit,
        Anonymize
    )
    from llm_guard import scan_prompt
    LLM_GUARD_AVAILABLE = True
except ImportError:
    LLM_GUARD_AVAILABLE = False
    print("⚠️ LLM Guard not installed. Install with: pip install llm-guard")


@dataclass
class AdvancedScanResult:
    """Result of advanced ML-based scan"""
    is_safe: bool
    risk_score: float
    triggered_scanners: List[str]
    sanitized_text: Optional[str] = None
    details: Dict = None


class AdvancedGuardrailsService:
    """
    Advanced guardrails using LLM Guard library.
    
    Protection levels:
    - standard: lightweight models (~50ms)
    - advanced: full models (~200ms)
    """
    
    def __init__(
        self,
        protection_level: str = "standard",
        prompt_injection_threshold: float = 0.5,
        toxicity_threshold: float = 0.7,
        ban_topics_threshold: float = 0.6,
        banned_topics: List[str] = None,
        allowed_languages: List[str] = None,
        max_tokens: int = 2048
    ):
        if not LLM_GUARD_AVAILABLE:
            raise ImportError(
                "LLM Guard is not installed. "
                "Install with: pip install llm-guard"
            )
        
        self.protection_level = protection_level
        self.scanners = []
        
        # 1. Prompt Injection Scanner
        use_onnx = protection_level == "advanced"
        self.scanners.append(
            PromptInjection(
                threshold=prompt_injection_threshold,
                use_onnx=use_onnx
            )
        )
        
        # 2. Toxicity Scanner
        if protection_level == "advanced":
            # Use full transformer model
            self.scanners.append(
                Toxicity(
                    threshold=toxicity_threshold,
                    model_name="unitary/toxic-bert"
                )
            )
        else:
            # Use lightweight model
            self.scanners.append(
                Toxicity(threshold=toxicity_threshold)
            )
        
        # 3. Ban Topics (semantic matching)
        if banned_topics:
            self.scanners.append(
                BanTopics(
                    topics=banned_topics,
                    threshold=ban_topics_threshold
                )
            )
        
        # 4. Secrets Detection
        self.scanners.append(Secrets())
        
        # 5. Language Validation
        if allowed_languages:
            self.scanners.append(
                LLMGuardLanguage(valid_languages=allowed_languages)
            )
        
        # 6. Token Limit
        self.scanners.append(
            TokenLimit(
                limit=max_tokens,
                encoding_name="cl100k_base"  # GPT-3.5/4 encoding
            )
        )
        
        # 7. PII Anonymization (optional)
        # Uncomment to enable PII detection
        # self.scanners.append(Anonymize())
    
    async def scan(self, text: str) -> AdvancedScanResult:
        """
        Run all scanners on the input text.
        
        Returns aggregated result with risk score and triggered scanners.
        """
        # Run LLM Guard scanners
        # Note: scan_prompt is synchronous, so we run it in executor
        loop = asyncio.get_event_loop()
        sanitized_prompt, results_valid, results_score = await loop.run_in_executor(
            None,
            scan_prompt,
            self.scanners,
            text
        )
        
        # Aggregate results
        triggered = []
        max_risk = 0.0
        
        for scanner_name, is_valid in results_valid.items():
            if not is_valid:
                triggered.append(scanner_name)
                # Get risk score for this scanner
                score = results_score.get(scanner_name, 0.0)
                max_risk = max(max_risk, score)
        
        is_safe = len(triggered) == 0
        
        return AdvancedScanResult(
            is_safe=is_safe,
            risk_score=max_risk,
            triggered_scanners=triggered,
            sanitized_text=sanitized_prompt if sanitized_prompt != text else None,
            details={"scores": results_score}
        )


# Singleton instance
_advanced_service: Optional[AdvancedGuardrailsService] = None


def get_advanced_guardrails_service(
    protection_level: str = "standard",
    prompt_injection_threshold: float = 0.5,
    toxicity_threshold: float = 0.7,
    ban_topics_threshold: float = 0.6,
    banned_topics: List[str] = None,
    allowed_languages: List[str] = None,
    max_tokens: int = 2048
) -> Optional[AdvancedGuardrailsService]:
    """
    Get or create singleton instance of advanced guardrails.
    
    Returns None if LLM Guard is not available.
    """
    if not LLM_GUARD_AVAILABLE:
        return None
    
    global _advanced_service
    if _advanced_service is None:
        _advanced_service = AdvancedGuardrailsService(
            protection_level=protection_level,
            prompt_injection_threshold=prompt_injection_threshold,
            toxicity_threshold=toxicity_threshold,
            ban_topics_threshold=ban_topics_threshold,
            banned_topics=banned_topics,
            allowed_languages=allowed_languages,
            max_tokens=max_tokens
        )
    return _advanced_service
