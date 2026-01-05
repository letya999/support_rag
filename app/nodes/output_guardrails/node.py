"""
Output Guardrails Node

Validates LLM responses before sending to user.
Should be placed right before cache storage or END.
"""
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.services.config_loader.loader import get_node_params, get_node_config
from app.nodes.output_guardrails.scanner import get_output_guardrails_service, OutputScanResult
from app.observability.tracing import observe


class OutputGuardrailsNode(BaseNode):
    """
    Output validation node.
    
    Validates LLM responses for:
    - Data leakage (PII, credentials)
    - Toxicity
    - Relevance to query
    - Hallucinations
    """
    
    def __init__(self):
        super().__init__("output_guardrails")
        
        # Load configuration
        self.params = get_node_params("output_guardrails")
        self.config = get_node_config("output_guardrails")
        
        # Protection settings
        self.protection_level = self.params.get("protection_level", "standard")
        self.action_mode = self.params.get("action_mode", "block")
        
        # Thresholds
        self.toxicity_threshold = self.params.get("toxicity_threshold", 0.7)
        self.relevance_threshold = self.params.get("relevance_threshold", 0.5)
        self.hallucination_threshold = self.params.get("hallucination_threshold", 0.6)
        
        # Enabled scanners
        self.scanners = self.params.get("scanners", {})
        
        # Fallback responses
        self.fallback_responses = self.config.get("fallback_responses", {})
        
        # Logging config
        self.logging_config = self.config.get("logging", {})
        
        # Initialize scanner service
        data_leakage_patterns = self.config.get("data_leakage_patterns", [])
        hallucination_indicators = self.config.get("hallucination_indicators", [])
        
        self.scanner = get_output_guardrails_service(
            data_leakage_patterns=data_leakage_patterns,
            hallucination_indicators=hallucination_indicators,
            relevance_threshold=self.relevance_threshold,
            hallucination_threshold=self.hallucination_threshold
        )
    
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate LLM response before sending to user.
        """
        final_answer = state.get("final_answer", "")
        user_input = state.get("user_input", "")
        
        # Skip if no answer to validate
        if not final_answer:
            return {}
        
        # Run security scan
        scan_result: OutputScanResult = await self.scanner.scan(
            response=final_answer,
            user_query=user_input,
            enabled_scanners=self.scanners
        )
        
        # Log scan results
        if self.logging_config.get("log_to_langfuse", True):
            self._log_scan_result(scan_result, final_answer)
        
        # Handle threats
        if not scan_result.is_safe:
            return await self._handle_threat(state, scan_result)
        
        # Safe output
        return {
            "output_guardrails_passed": True,
            "output_risk_score": scan_result.risk_score
        }
    
    async def _handle_threat(
        self,
        state: Dict[str, Any],
        scan_result: OutputScanResult
    ) -> Dict[str, Any]:
        """Handle detected security threat in output"""
        
        if self.action_mode == "block":
            # Block response and return safe fallback
            language = state.get("detected_language", "en")
            fallback_msg = self.fallback_responses.get(
                language,
                self.fallback_responses.get("default", "I cannot provide this response.")
            )
            
            if self.logging_config.get("log_blocked_responses", True):
                print(f"🛡️ Blocked unsafe response. Risk: {scan_result.risk_score:.2f}, "
                      f"Triggers: {', '.join(scan_result.triggered_scanners)}")
            
            return {
                "final_answer": fallback_msg,
                "output_guardrails_blocked": True,
                "output_risk_score": scan_result.risk_score,
                "output_triggers": scan_result.triggered_scanners
            }
        
        elif self.action_mode == "log":
            # Log but allow response
            print(f"⚠️ Suspicious output detected. Risk: {scan_result.risk_score:.2f}, "
                  f"Triggers: {', '.join(scan_result.triggered_scanners)}")
            
            return {
                "output_guardrails_warning": True,
                "output_risk_score": scan_result.risk_score,
                "output_triggers": scan_result.triggered_scanners
            }
        
        elif self.action_mode == "sanitize":
            # Use sanitized version if available
            if scan_result.sanitized_text:
                if self.logging_config.get("log_sanitized_responses", True):
                    print(f"🧹 Sanitized output. Risk: {scan_result.risk_score:.2f}")
                
                return {
                    "final_answer": scan_result.sanitized_text,
                    "output_guardrails_sanitized": True,
                    "output_risk_score": scan_result.risk_score
                }
        
        return {}
    
    def _log_scan_result(self, scan_result: OutputScanResult, original_text: str):
        """Log scan results for monitoring"""
        log_data = {
            "is_safe": scan_result.is_safe,
            "risk_score": scan_result.risk_score,
            "triggered_scanners": scan_result.triggered_scanners,
        }
        
        # Include original only if configured
        if self.logging_config.get("include_original_response", False):
            log_data["original_response"] = original_text
        
        if scan_result.details:
            log_data["details"] = scan_result.details
        
        return log_data


# Singleton instance for graph integration
output_guardrails_node = OutputGuardrailsNode()
