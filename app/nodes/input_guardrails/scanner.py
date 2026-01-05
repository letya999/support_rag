"""
Input Guardrails Scanner Service

Provides protection against:
- Prompt injection
- Toxic content
- Jailbreak attempts
- Sensitive data leakage
"""
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import asyncio
from functools import lru_cache


@dataclass
class ScanResult:
    """Result of a security scan"""
    is_safe: bool
    risk_score: float  # 0.0 - 1.0
    triggered_scanners: List[str]
    sanitized_text: Optional[str] = None
    details: Dict = None


class RegexScanner:
    """Fast regex-based pattern matching"""
    
    def __init__(self, patterns: List[Dict]):
        self.patterns = [
            {
                "regex": re.compile(p["pattern"], re.IGNORECASE | re.MULTILINE),
                "description": p["description"]
            }
            for p in patterns
        ]
    
    def scan(self, text: str) -> Tuple[bool, float, List[str]]:
        """
        Returns: (is_safe, risk_score, triggered_patterns)
        """
        triggered = []
        for pattern in self.patterns:
            if pattern["regex"].search(text):
                triggered.append(pattern["description"])
        
        is_safe = len(triggered) == 0
        risk_score = min(1.0, len(triggered) * 0.3)  # Each match adds 0.3
        
        return is_safe, risk_score, triggered


class TokenLimitScanner:
    """Check input length"""
    
    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
    
    def scan(self, text: str) -> Tuple[bool, float]:
        """
        Simple approximation: 1 token ≈ 4 characters
        For exact counting, use tiktoken
        """
        estimated_tokens = len(text) // 4
        is_safe = estimated_tokens <= self.max_tokens
        risk_score = 0.0 if is_safe else min(1.0, estimated_tokens / self.max_tokens - 1.0)
        
        return is_safe, risk_score


class LanguageScanner:
    """Validate input language"""
    
    def __init__(self, allowed_languages: List[str]):
        self.allowed_languages = set(allowed_languages)
    
    def scan(self, text: str, detected_language: Optional[str] = None) -> Tuple[bool, float]:
        """
        If detected_language is provided (from language_detection node),
        use it. Otherwise, do simple heuristic check.
        """
        if detected_language:
            is_safe = detected_language in self.allowed_languages
            risk_score = 0.0 if is_safe else 0.5
            return is_safe, risk_score
        
        # Simple heuristic: check for Cyrillic characters
        has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
        has_latin = bool(re.search(r'[a-zA-Z]', text))
        
        if "ru" in self.allowed_languages and has_cyrillic:
            return True, 0.0
        if "en" in self.allowed_languages and has_latin:
            return True, 0.0
        
        # Unknown language
        return False, 0.3


class SecretsScanner:
    """Detect API keys, tokens, passwords"""
    
    # Common patterns for secrets
    PATTERNS = [
        (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', "API Key"),
        (r'(?i)(bearer|token)\s+([a-zA-Z0-9_\-\.]{20,})', "Bearer Token"),
        (r'sk-[a-zA-Z0-9]{20,}', "OpenAI API Key"),
        (r'ghp_[a-zA-Z0-9]{36}', "GitHub Token"),
        (r'(?i)password\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', "Password"),
    ]
    
    def __init__(self):
        self.compiled_patterns = [
            (re.compile(pattern, re.MULTILINE), name)
            for pattern, name in self.PATTERNS
        ]
    
    def scan(self, text: str) -> Tuple[bool, float, List[str]]:
        """Returns: (is_safe, risk_score, found_secrets)"""
        found = []
        for pattern, name in self.compiled_patterns:
            if pattern.search(text):
                found.append(name)
        
        is_safe = len(found) == 0
        risk_score = 1.0 if found else 0.0  # High risk if secrets detected
        
        return is_safe, risk_score, found


class BasicGuardrailsService:
    """
    Basic (fast) guardrails using regex and heuristics.
    No ML models required. Latency: ~5-10ms
    """
    
    def __init__(
        self,
        regex_patterns: List[Dict],
        max_tokens: int,
        allowed_languages: List[str]
    ):
        self.regex_scanner = RegexScanner(regex_patterns)
        self.token_scanner = TokenLimitScanner(max_tokens)
        self.language_scanner = LanguageScanner(allowed_languages)
        self.secrets_scanner = SecretsScanner()
    
    async def scan(
        self,
        text: str,
        detected_language: Optional[str] = None,
        enabled_scanners: Dict[str, bool] = None
    ) -> ScanResult:
        """
        Run all enabled scanners and aggregate results.
        """
        if enabled_scanners is None:
            enabled_scanners = {
                "regex_patterns": True,
                "token_limit": True,
                "language": True,
                "secrets": True
            }
        
        triggered = []
        max_risk = 0.0
        details = {}
        
        # 1. Regex patterns
        if enabled_scanners.get("regex_patterns", True):
            is_safe, risk, patterns = self.regex_scanner.scan(text)
            if not is_safe:
                triggered.append("regex_patterns")
                details["regex_patterns"] = patterns
            max_risk = max(max_risk, risk)
        
        # 2. Token limit
        if enabled_scanners.get("token_limit", True):
            is_safe, risk = self.token_scanner.scan(text)
            if not is_safe:
                triggered.append("token_limit")
                details["token_limit"] = "Input exceeds token limit"
            max_risk = max(max_risk, risk)
        
        # 3. Language
        if enabled_scanners.get("language", True):
            is_safe, risk = self.language_scanner.scan(text, detected_language)
            if not is_safe:
                triggered.append("language")
                details["language"] = f"Unsupported language: {detected_language}"
            max_risk = max(max_risk, risk)
        
        # 4. Secrets
        if enabled_scanners.get("secrets", True):
            is_safe, risk, secrets = self.secrets_scanner.scan(text)
            if not is_safe:
                triggered.append("secrets")
                details["secrets"] = secrets
            max_risk = max(max_risk, risk)
        
        return ScanResult(
            is_safe=len(triggered) == 0,
            risk_score=max_risk,
            triggered_scanners=triggered,
            details=details
        )


# Singleton instance
_basic_service: Optional[BasicGuardrailsService] = None


def get_basic_guardrails_service(
    regex_patterns: List[Dict],
    max_tokens: int,
    allowed_languages: List[str]
) -> BasicGuardrailsService:
    """Get or create singleton instance"""
    global _basic_service
    if _basic_service is None:
        _basic_service = BasicGuardrailsService(
            regex_patterns=regex_patterns,
            max_tokens=max_tokens,
            allowed_languages=allowed_languages
        )
    return _basic_service
