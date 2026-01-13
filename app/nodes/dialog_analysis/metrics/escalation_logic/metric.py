import os
import json
import yaml
from typing import Any, Dict, List
from app.nodes.dialog_analysis.metrics.base import DialogAnalysisBaseMetric
from app.logging_config import logger
from app.integrations.llm import get_llm
from app.nodes.state_machine.states_config import SIGNAL_ESCALATION_REQ


class EscalationLogicValidation(DialogAnalysisBaseMetric):
    """
    Hybrid metric: Rule-based check + LLM validation for escalation logic.
    
    Validates escalation decision against expected logic:
    - Explicit request OR
    - High anger (>0.7) OR
    - Safety violation
    """
    
    def __init__(self):
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        
        # Load prompt template
        prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()
        
        # Initialize LLM for validation
        self.llm = get_llm(
            model=self.config.get("model", "gpt-4o-mini"),
            temperature=self.config.get("temperature", 0.0),
            json_mode=self.config.get("json_mode", True)
        )
        
        self.anger_threshold = self.config.get("anger_threshold", 0.7)
    
    def _rule_based_check(self, dialog_analysis: Dict, sentiment: Dict, safety_violation: bool, 
                         escalation_decision: str) -> Dict[str, Any]:
        """
        Rule-based validation of escalation logic.
        
        Returns:
            Dict with rule_compliance, expected_decision, trigger
        """
        # Extract signals
        explicit_request = dialog_analysis.get(SIGNAL_ESCALATION_REQ, False)
        
        # Check anger
        sentiment_label = sentiment.get("label", "neutral") if isinstance(sentiment, dict) else "neutral"
        sentiment_score = sentiment.get("score", 0.0) if isinstance(sentiment, dict) else 0.0
        high_anger = (sentiment_label in ["angry", "frustrated"]) and (sentiment_score > self.anger_threshold)
        
        # Determine expected decision
        should_escalate = explicit_request or high_anger or safety_violation
        expected_decision = "escalate" if should_escalate else "auto_reply"
        
        # Check compliance
        follows_logic = (escalation_decision == expected_decision)
        
        # Identify trigger
        trigger = None
        if explicit_request:
            trigger = "explicit_request"
        elif high_anger:
            trigger = f"high_anger (score={sentiment_score:.2f})"
        elif safety_violation:
            trigger = "safety_violation"
        else:
            trigger = "none"
        
        return {
            "follows_logic": follows_logic,
            "expected_decision": expected_decision,
            "actual_decision": escalation_decision,
            "trigger": trigger,
            "explicit_request": explicit_request,
            "high_anger": high_anger,
            "safety_violation": safety_violation
        }
    
    def _format_history(self, history: List) -> str:
        """Format conversation history for prompt."""
        if not history:
            return "No previous conversation"
        
        formatted = []
        for msg in history[-3:]:  # Last 3 messages
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
            else:
                role = getattr(msg, "type", "unknown")
                content = getattr(msg, "content", "")
            formatted.append(f"{role.upper()}: {content}")
        
        return "\n".join(formatted)
    
    def calculate(self, expected: Any, actual: Any, **kwargs) -> float:
        """
        Calculate escalation logic validation score (hybrid approach).
        
        Args:
            expected: Not used (reference-free)
            actual: Not used directly
            **kwargs: Should contain dialog analysis output fields
            
        Returns:
            float: Combined validation score 0-1
        """
        question = kwargs.get("question", "")
        conversation_history = kwargs.get("conversation_history", [])
        dialog_analysis = kwargs.get("dialog_analysis", {})
        sentiment = kwargs.get("sentiment", {})
        safety_violation = kwargs.get("safety_violation", False)
        escalation_decision = kwargs.get("escalation_decision", "auto_reply")
        escalation_reason = kwargs.get("escalation_reason", "")
        
        if not dialog_analysis:
            return 0.0
        
        # 1. Rule-based check
        rule_check = self._rule_based_check(
            dialog_analysis, sentiment, safety_violation, escalation_decision
        )
        
        rule_compliance_score = 1.0 if rule_check["follows_logic"] else 0.0
        
        # 2. LLM validation for qualitative aspects
        sentiment_label = sentiment.get("label", "neutral") if isinstance(sentiment, dict) else "neutral"
        sentiment_score = sentiment.get("score", 0.0) if isinstance(sentiment, dict) else 0.0
        history_text = self._format_history(conversation_history)
        
        prompt = self.prompt_template.format(
            question=question,
            conversation_history=history_text,
            dialog_analysis=json.dumps(dialog_analysis, ensure_ascii=False),
            sentiment_label=sentiment_label,
            sentiment_score=sentiment_score,
            safety_violation=safety_violation,
            escalation_decision=escalation_decision,
            escalation_reason=escalation_reason or "No reason provided",
            rule_check_result=json.dumps(rule_check, ensure_ascii=False)
        )
        
        try:
            # Invoke LLM
            response = self.llm.invoke([{"role": "user", "content": prompt}])
            content = response.content
            
            # Parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            llm_score = result.get("llm_validation_score", 0.5)
            llm_score = max(0.0, min(1.0, float(llm_score)))
            
        except Exception as e:
            logger.error("EscalationLogicValidation LLM part failed", extra={"error": str(e)})
            llm_score = 0.5  # Neutral if LLM fails
        
        # 3. Combined score: rule compliance (70%) + LLM validation (30%)
        combined_score = (rule_compliance_score * 0.7) + (llm_score * 0.3)
        
        return max(0.0, min(1.0, combined_score))
