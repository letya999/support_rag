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
from app.pipeline.state import State
from app.nodes.base_node import BaseNode
from app.services.config_loader.loader import get_node_params, get_node_config
from app.nodes.input_guardrails.scanner import get_basic_guardrails_service, ScanResult
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
        
        # Initialize scanner service
        regex_patterns = self.config.get("regex_patterns", [])
        self.scanner = get_basic_guardrails_service(
            regex_patterns=regex_patterns,
            max_tokens=self.max_input_tokens,
            allowed_languages=self.allowed_languages
        )
    
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scan user input for security threats.
        
        If threat detected:
        - block mode: return safe rejection message
        - log mode: log event and continue
        - sanitize mode: remove malicious parts and continue
        """
        user_input = state.get("user_input", "")
        detected_language = state.get("detected_language")
        
        # Run security scan
        scan_result: ScanResult = await self.scanner.scan(
            text=user_input,
            detected_language=detected_language,
            enabled_scanners=self.scanners
        )
        
        # Log scan results
        if self.logging_config.get("log_to_langfuse", True):
            self._log_scan_result(scan_result, user_input)
        
        # Handle threats
        if not scan_result.is_safe:
            return await self._handle_threat(state, scan_result)
        
        # Safe input - continue processing
        state["guardrails_passed"] = True
        state["guardrails_risk_score"] = scan_result.risk_score
        
        return state
    
    async def _handle_threat(self, state: State, scan_result: ScanResult) -> State:
        """
        Handle detected security threat based on action_mode.
        """
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
            
            state["final_answer"] = rejection_msg
            state["action"] = "auto_reply"  # Skip to generation
            
            # Log blocked request
            if self.logging_config.get("log_blocked_requests", True):
                print(f"🛡️ Blocked malicious request. Risk: {scan_result.risk_score:.2f}, "
                      f"Triggers: {', '.join(scan_result.triggered_scanners)}")
        
        elif self.action_mode == "log":
            # Log but continue processing
            state["guardrails_warning"] = True
            state["guardrails_risk_score"] = scan_result.risk_score
            state["guardrails_triggered"] = scan_result.triggered_scanners
            
            print(f"⚠️ Suspicious request detected. Risk: {scan_result.risk_score:.2f}, "
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


# Singleton instance for graph integration
input_guardrails_node = InputGuardrailsNode()
