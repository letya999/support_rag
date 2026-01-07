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
from app.services.config_loader.loader import get_node_params, get_node_config
from app.nodes.input_guardrails.scanner import get_basic_guardrails_service, ScanResult
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
    """
    
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
        """Initialize the scanner service (Load models)"""
        # Force reset singleton to pick up new config
        reset_advanced_service()
        self.scanner = None

        regex_patterns = self.config.get("regex_patterns", [])
        
        # Try initializing advanced guardrails if configured
        if self.protection_level in ["standard", "advanced"]:
            print(f"🛡️ Initializing Advanced Guardrails (level: {self.protection_level})...")
            print(f"   Thresholds: PI={self.prompt_injection_threshold}, Tox={self.toxicity_threshold}, Topics={self.ban_topics_threshold}")
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
                print("⚠️ Advanced guardrails unavailable. Falling back to Basic Guardrails.")
            
            self.scanner = get_basic_guardrails_service(
                regex_patterns=regex_patterns,
                max_tokens=self.max_input_tokens,
                allowed_languages=self.allowed_languages
            )
        print("✅ Input Guardrails Ready")
    
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """

        Scan user input for security threats.
        
        Contracts:
            - Required Inputs: `question` (str)
            - Optional Inputs: `detected_language` (str)
            - Guaranteed Outputs: `guardrails_passed` (bool) OR `guardrails_blocked` (bool), `guardrails_risk_score` (float), `guardrails_triggered` (List[str])
            - Conditional Outputs: `guardrails_warning` (bool), `guardrails_sanitized` (bool), `user_input` (modified), `answer` (if blocked), `action` (if blocked)
        
        If threat detected:
        - block mode: return safe rejection message
        - log mode: log event and continue
        - sanitize mode: remove malicious parts and continue
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
               if self.protection_level == "basic" or isinstance(self.scanner, type(get_basic_guardrails_service([], 0, []))) 
               else {})
        )
        
        # Log scan results
        if self.logging_config.get("log_to_langfuse", True):
            self._log_scan_result(scan_result, user_input)
        
        # Handle threats (with support-context override)
        if not scan_result.is_safe:
            return await self._handle_threat(state, scan_result, is_whitelisted)
        
        # Safe input - continue processing
        state["guardrails_passed"] = True
        state["guardrails_risk_score"] = scan_result.risk_score
        
        return state
    
    async def _handle_threat(self, state: State, scan_result: ScanResult, is_whitelisted: bool = False) -> State:
        """
        Handle detected security threat based on action_mode.
        """
        # Override: If whitelisted support query, downgrade non-critical threats to warnings
        if is_whitelisted:
            non_critical = {"BanTopics", "Toxicity"}
            remaining_threats = [t for t in scan_result.triggered_scanners if t not in non_critical]
            
            if not remaining_threats:
                # Only non-critical scanners triggered - treat as warning
                print(f"🟡 Support query flagged but whitelisted: {scan_result.triggered_scanners} (Risk: {scan_result.risk_score:.2f})")
                state["guardrails_warning"] = True
                state["guardrails_risk_score"] = scan_result.risk_score
                state["guardrails_triggered"] = scan_result.triggered_scanners
                return state
        
        if self.action_mode == "block":
            # Block request and return safe message
            state["guardrails_blocked"] = True
            state["guardrails_risk_score"] = scan_result.risk_score
            state["guardrails_triggered"] = scan_result.triggered_scanners
            
            # Set safe rejection message
            language = state.get("detected_language", "en")
            rejection_msg = self.rejection_messages.get(
                language,
                self.rejection_messages.get("default", "I cannot process this request.")
            )
            
            state["answer"] = rejection_msg
            state["action"] = "auto_reply"  # Skip to generation
            
            # Log blocked request
            if self.logging_config.get("log_blocked_requests", True):
                print(f"🛡️ Blocked malicious request. Risk: {scan_result.risk_score:.2f}, "
                      f"Triggers: {', '.join(scan_result.triggered_scanners)}")
        
        elif self.action_mode == "log":
            # Check for critical threats that MUST be blocked regardless of mode
            critical_threats = ["PromptInjection", "Secrets"]
            has_critical_threat = any(t in scan_result.triggered_scanners for t in critical_threats)
            
            if has_critical_threat:
                # Force block for critical security threats
                print(f"🛑 CRITICAL THREAT DETECTED in 'log' mode. Enforcing block. Triggers: {scan_result.triggered_scanners}")
                
                state["guardrails_blocked"] = True
                state["guardrails_risk_score"] = scan_result.risk_score
                state["guardrails_triggered"] = scan_result.triggered_scanners
                
                # Set safe rejection message
                language = state.get("detected_language", "en")
                rejection_msg = self.rejection_messages.get(
                    language,
                    self.rejection_messages.get("default", "I cannot process this request.")
                )
                
                state["answer"] = rejection_msg
                state["action"] = "auto_reply"
                return state

            # Log but continue processing for non-critical threats (Toxicity, BanTopics)
            state["guardrails_warning"] = True
            state["guardrails_risk_score"] = scan_result.risk_score
            state["guardrails_triggered"] = scan_result.triggered_scanners
            
            print(f"⚠️ Suspicious request detected (Allowed in log mode). Risk: {scan_result.risk_score:.2f}, "
                  f"Triggers: {', '.join(scan_result.triggered_scanners)}")
        
        elif self.action_mode == "sanitize":
            # Sanitize and continue
            if scan_result.sanitized_text:
                state["user_input"] = scan_result.sanitized_text
                state["guardrails_sanitized"] = True
                
                if self.logging_config.get("log_sanitized_requests", True):
                    print(f"🧹 Sanitized request. Risk: {scan_result.risk_score:.2f}")
        
        return state
    
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
