from typing import Dict, Any
from app.nodes.base_node import BaseEvaluator
from app.nodes.dialog_analysis.metrics import (
    SentimentCoherence,
    EscalationLogicValidation,
    ContextIntegration
)


class DialogAnalysisEvaluator(BaseEvaluator):
    """Evaluator for dialog analysis node outputs using LLM-based metrics."""
    
    def __init__(self):
        super().__init__()
        self.sentiment_coherence = SentimentCoherence()
        self.escalation_logic = EscalationLogicValidation()
        self.context_integration = ContextIntegration()
        self.metrics = [
            self.sentiment_coherence,
            self.escalation_logic,
            self.context_integration
        ]
    
    def calculate_metrics(self, state: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate all dialog analysis metrics from state.
        
        Args:
            state: Pipeline state dictionary containing:
                - question: str
                - conversation_history: List
                - dialog_analysis: Dict (output from dialog_analysis node)
                - sentiment: Dict (output from dialog_analysis node)
                - safety_violation: bool
                - safety_reason: str (optional)
                - escalation_decision: str
                - escalation_reason: str (optional)
                
        Returns:
            Dict[str, float]: Metric scores
        """
        question = state.get("question", "")
        conversation_history = state.get("conversation_history", [])
        dialog_analysis = state.get("dialog_analysis", {})
        sentiment = state.get("sentiment", {})
        safety_violation = state.get("safety_violation", False)
        safety_reason = state.get("safety_reason")
        escalation_decision = state.get("escalation_decision", "auto_reply")
        escalation_reason = state.get("escalation_reason")
        
        if not dialog_analysis:
            return {
                "sentiment_coherence": 0.0,
                "escalation_logic_validation": 0.0,
                "context_integration": 0.0
            }
        

        return {
            "sentiment_coherence": self.sentiment_coherence.calculate(
                None, None,
                question=question,
                conversation_history=conversation_history,
                sentiment=sentiment
            ),
            "escalation_logic_validation": self.escalation_logic.calculate(
                None, None,
                question=question,
                conversation_history=conversation_history,
                dialog_analysis=dialog_analysis,
                sentiment=sentiment,
                safety_violation=safety_violation,
                escalation_decision=escalation_decision,
                escalation_reason=escalation_reason
            ),
            "context_integration": self.context_integration.calculate(
                None, None,
                question=question,
                conversation_history=conversation_history,
                dialog_analysis=dialog_analysis
            )
        }

    async def evaluate_single(self, question: str, conversation_history: list = None) -> Dict[str, Any]:
        """
        Run the node on one item and calculate metrics.
        """
        from app.nodes.dialog_analysis.node import dialog_analysis_node
        
        state = {
            "question": question,
            "conversation_history": conversation_history or []
        }
        
        # Execute node
        result = await dialog_analysis_node.execute(state)
        
        # Update state with result for metric calculation
        state.update(result)
        
        # Calculate metrics
        metrics = self.calculate_metrics(state)
        
        return {
            "question": question,
            "result": result,
            "metrics": metrics
        }


evaluator = DialogAnalysisEvaluator()
