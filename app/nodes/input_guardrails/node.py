"""
Input Guardrails Node

Protects the pipeline from malicious inputs:
- Prompt injection attacks
- Toxic content
- Jailbreak attempts
- Sensitive data leakage
- Off-topic requests

This node should be placed early in the pipeline, ideally right after
session_starter and before language_detection.
"""
from typing import Dict, Any
import re
from app.pipeline.state import State
from app.nodes.base_node import BaseNode
from app.logging_config import logger
from app.services.config_loader.loader import get_node_params, get_node_config
from app.nodes.input_guardrails.scanner import get_basic_guardrails_service, ScanResult, BasicGuardrailsService, reset_basic_service
from app.nodes.input_guardrails.advanced_scanner import get_advanced_guardrails_service, AdvancedScanResult, reset_advanced_service
from app.observability.tracing import observe


class InputGuardrailsNode(BaseNode):
    """
    Input validation and security scanning node.
    
    Checks user input for:
    - Prompt injection patterns
    - Malicious content
    - Token limits
    - Language validation
    - Secrets/credentials
    
    Contracts:
        Input:
            Required:
                - question (str): User's input text to scan
            Optional:
                - detected_language (str): Language hint for scanner
        
        Output:
            Guaranteed:
                - guardrails_risk_score (float): Risk score 0.0-1.0
            Conditional (when threat detected):
                - guardrails_passed (bool): True if safe
                - guardrails_blocked (bool): True if blocked
                - guardrails_warning (bool): True if suspicious but allowed
                - guardrails_sanitized (bool): True if text was sanitized
                - guardrails_triggered (List[str]): List of triggered scanners
                - answer (str): Rejection message if blocked
                - action (str): 'auto_reply' if blocked
    """
    
    INPUT_CONTRACT = {
        "required": ["question"],
        "optional": ["detected_language"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["guardrails_risk_score"],
        "conditional": [
            "guardrails_passed",
            "guardrails_blocked",
            "guardrails_warning",
            "guardrails_sanitized",
            "guardrails_triggered",
            "answer",
            "action"
        ]
    }
    
    def __init__(self):
        super().__init__("input_guardrails")
        
        # Load configuration
        self.params = get_node_params("input_guardrails")
        self.config = get_node_config("input_guardrails")
        
        # Protection settings
        self.protection_level = self.params.get("protection_level", "standard")
        self.action_mode = self.params.get("action_mode", "block")
        
        # Thresholds
        self.prompt_injection_threshold = self.params.get("prompt_injection_threshold", 0.5)
        self.toxicity_threshold = self.params.get("toxicity_threshold", 0.7)
        self.ban_topics_threshold = self.params.get("ban_topics_threshold", 0.6)
        
        # Token limits
        self.max_input_tokens = self.params.get("max_input_tokens", 2048)
        
        # Allowed languages
        self.allowed_languages = self.params.get("allowed_languages", ["ru", "en"])
        
        # Enabled scanners
        self.scanners = self.params.get("scanners", {})
        
        # Rejection messages
        self.rejection_messages = self.config.get("rejection_messages", {})
        
        # Logging config
        self.logging_config = self.config.get("logging", {})
        
        # Support-context whitelist (terms that are normal in support but trigger false positives)
        self.support_whitelist_patterns = [
            r"(?i)(black|white)\s+(screen|page)",  # "black screen" is a technical issue
            r"(?i)(login|password|credentials|authentication)",  # Auth issues are normal
            r"(?i)(won't accept|can't log in|error logging)",  # Login problems
            r"(?i)(website|app|service).*(down|slow|not working)",  # Service issues
            r"(?i)(crazy|insane|ridiculous).*(website|service|app|support)",  # Frustrated users
        ]
        
        # Initialize scanner service (Lazy load)
        self.scanner = None
        
    async def warmup(self):
        """
        Initialize the scanner service and load models.
        Should be called during startup or configuration reload.
        """
        # Force reset singleton to pick up new config
        reset_advanced_service()
        reset_basic_service()
        self.scanner = None

        regex_patterns = self.config.get("regex_patterns", [])
        
        # Try initializing advanced guardrails if configured
        if self.protection_level in ["standard", "advanced"]:
            logger.info("Initializing Advanced Guardrails", extra={
                "level": self.protection_level,
                "pi_threshold": self.prompt_injection_threshold,
                "tox_threshold": self.toxicity_threshold,
                "topics_threshold": self.ban_topics_threshold
            })
            # Run in executor to avoid blocking loop if necessary, though init might be sync
            self.scanner = get_advanced_guardrails_service(
                protection_level=self.protection_level,
                prompt_injection_threshold=self.prompt_injection_threshold,
                toxicity_threshold=self.toxicity_threshold,
                ban_topics_threshold=self.ban_topics_threshold,
                banned_topics=self.config.get("banned_topics", []),
                allowed_languages=self.allowed_languages,
                max_tokens=self.max_input_tokens
            )
            
        # Fallback to basic guardrails if advanced is not available or requested
        if self.scanner is None:
            if self.protection_level != "basic":
                logger.warning("Advanced guardrails unavailable, falling back to basic")
            
            self.scanner = get_basic_guardrails_service(
                regex_patterns=regex_patterns,
                max_tokens=self.max_input_tokens,
                allowed_languages=self.allowed_languages
            )
        logger.info("Input Guardrails ready")
    
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scan user input for security threats and malicious content.

        Args:
            state: Current pipeline state

        Returns:
            Dict: State updates including safety flags and risk scores
        """
        # State uses 'question' not 'user_input'
        user_input = state.get("question", "")
        detected_language = state.get("detected_language")
        
        # Ensure scanner is loaded (Lazy load fallback)
        if self.scanner is None:
            await self.warmup()
        
        # Check if this looks like a legitimate support query (whitelist)
        is_whitelisted = self._is_support_query(user_input)
        
        # Run security scan
        scan_result = await self.scanner.scan(
            text=user_input,
            **({"detected_language": detected_language, "enabled_scanners": self.scanners} 
               if self.protection_level == "basic" or isinstance(self.scanner, BasicGuardrailsService) 
               else {})
        )
        
        # Log scan results
        if self.logging_config.get("log_to_langfuse", True):
            self._log_scan_result(scan_result, user_input)
        
        # Handle threats (with support-context override)
        if not scan_result.is_safe:
            return await self._handle_threat(scan_result, is_whitelisted, state.get("detected_language", "en"))
        
        # Safe input - continue processing
        # Return ONLY the changes, not the whole state (fixes State Bloat)
        return {
            "guardrails_passed": True,
            "guardrails_risk_score": scan_result.risk_score
        }
    
    async def _handle_threat(
        self, 
        scan_result: ScanResult, 
        is_whitelisted: bool = False,
        detected_language: str = "en"
    ) -> Dict[str, Any]:
        """
        Handle detected security threat based on action_mode.
        
        Returns ONLY the fields to update (not the whole state).
        """
        # Override: If whitelisted support query, downgrade non-critical threats to warnings
        if is_whitelisted:
            non_critical = {"BanTopics", "Toxicity"}
            remaining_threats = [t for t in scan_result.triggered_scanners if t not in non_critical]
            
            if not remaining_threats:
                # Only non-critical scanners triggered - treat as warning
                logger.info("Support query flagged but whitelisted", extra={"triggers": scan_result.triggered_scanners, "risk": scan_result.risk_score})
                return {
                    "guardrails_warning": True,
                    "guardrails_risk_score": scan_result.risk_score,
                    "guardrails_triggered": scan_result.triggered_scanners
                }
        
        if self.action_mode == "block":
            # Block request and return safe message
            rejection_msg = self.rejection_messages.get(
                detected_language,
                self.rejection_messages.get("default", "I cannot process this request.")
            )
            
            # Log blocked request
            if self.logging_config.get("log_blocked_requests", True):
                logger.warning("Blocked malicious request", extra={"risk": scan_result.risk_score, "triggers": scan_result.triggered_scanners})
            
            return {
                "guardrails_blocked": True,
                "guardrails_risk_score": scan_result.risk_score,
                "guardrails_triggered": scan_result.triggered_scanners,
                "answer": rejection_msg,
                "action": "auto_reply"
            }
        
        elif self.action_mode == "log":
            # Check for critical threats that MUST be blocked regardless of mode
            critical_threats = ["PromptInjection", "Secrets"]
            has_critical_threat = any(t in scan_result.triggered_scanners for t in critical_threats)
            
            if has_critical_threat:
                # Force block for critical security threats
                logger.error("CRITICAL THREAT DETECTED in log mode, enforcing block", extra={"triggers": scan_result.triggered_scanners})
                
                rejection_msg = self.rejection_messages.get(
                    detected_language,
                    self.rejection_messages.get("default", "I cannot process this request.")
                )
                
                return {
                    "guardrails_blocked": True,
                    "guardrails_risk_score": scan_result.risk_score,
                    "guardrails_triggered": scan_result.triggered_scanners,
                    "answer": rejection_msg,
                    "action": "auto_reply"
                }

            # Log but continue processing for non-critical threats (Toxicity, BanTopics)
            logger.warning("Suspicious request detected (log mode)", extra={"risk": scan_result.risk_score, "triggers": scan_result.triggered_scanners})
            
            return {
                "guardrails_warning": True,
                "guardrails_risk_score": scan_result.risk_score,
                "guardrails_triggered": scan_result.triggered_scanners
            }
        
        elif self.action_mode == "sanitize":
            # Sanitize and continue
            if scan_result.sanitized_text:
                if self.logging_config.get("log_sanitized_requests", True):
                    logger.info("Sanitized request", extra={"risk": scan_result.risk_score})
                
                return {
                    "question": scan_result.sanitized_text,  # Update question with sanitized text
                    "guardrails_sanitized": True,
                    "guardrails_risk_score": scan_result.risk_score
                }
        
        # Default fallback - pass through
        return {
            "guardrails_risk_score": scan_result.risk_score
        }
    
    def _log_scan_result(self, scan_result: ScanResult, original_text: str):
        """Log scan results for monitoring"""
        log_data = {
            "is_safe": scan_result.is_safe,
            "risk_score": scan_result.risk_score,
            "triggered_scanners": scan_result.triggered_scanners,
        }
        
        # Include original text only if configured (privacy concern)
        if self.logging_config.get("include_original_text", False):
            log_data["original_text"] = original_text
        
        if scan_result.details:
            log_data["details"] = scan_result.details
        
        # This will be captured by Langfuse via @observe decorator
        return log_data
    
    def _is_support_query(self, text: str) -> bool:
        """
        Check if text matches support-related patterns that might trigger false positives.
        
        Examples:
        - "black screen" (technical issue, not racial content)
        - "password error" (auth issue, not prompt injection)
        - "you guys are crazy" (frustrated user, not abuse)
        """
        for pattern in self.support_whitelist_patterns:
            if re.search(pattern, text):
                return True
        return False


# Singleton instance for graph integration
input_guardrails_node = InputGuardrailsNode()
