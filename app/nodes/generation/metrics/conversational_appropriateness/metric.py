import os
import json
import yaml
from typing import Any, Dict, List
from app.nodes.generation.metrics.base import GenerationBaseMetric
from app.integrations.llm import get_llm


class ConversationalAppropriateness(GenerationBaseMetric):
    """LLM-as-judge metric to evaluate answer appropriateness for customer support."""
    
    def __init__(self):
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        
        # Load prompt template
        prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()
        
        # Initialize LLM
        self.llm = get_llm(
            model=self.config.get("model", "gpt-4o-mini"),
            temperature=self.config.get("temperature", 0.0),
            json_mode=self.config.get("json_mode", True)
        )
    
    def _format_history(self, history: List) -> str:
        """Format conversation history for prompt."""
        if not history:
            return "No previous conversation"
        
        formatted = []
        for msg in history[-5:]:  # Last 5 messages
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
        Calculate conversational appropriateness score.
        
        Args:
            expected: Not used (reference-free)
            actual: The generated answer
            **kwargs: Should contain 'question', 'conversation_history', 'sentiment'
            
        Returns:
            float: Overall appropriateness score 0-1
        """
        question = kwargs.get("question", "")
        conversation_history = kwargs.get("conversation_history", [])
        sentiment = kwargs.get("sentiment", {})
        
        if not question or not actual:
            return 0.0
        
        # Extract sentiment info
        sentiment_label = sentiment.get("label", "neutral") if isinstance(sentiment, dict) else "neutral"
        sentiment_score = sentiment.get("score", 0.0) if isinstance(sentiment, dict) else 0.0
        
        # Format conversation history
        history_text = self._format_history(conversation_history)
        
        # Format prompt
        prompt = self.prompt_template.format(
            conversation_history=history_text,
            question=question,
            sentiment_label=sentiment_label,
            sentiment_score=sentiment_score,
            answer=actual
        )
        
        try:
            # Invoke LLM
            response = self.llm.invoke([{"role": "user", "content": prompt}])
            content = response.content
            
            # Parse JSON (handle markdown wrapping)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            score = result.get("overall_appropriateness", 0.0)
            
            # Validate score range
            return max(0.0, min(1.0, float(score)))
            
        except Exception as e:
            print(f"⚠️ ConversationalAppropriateness evaluation failed: {e}")
            return 0.0
