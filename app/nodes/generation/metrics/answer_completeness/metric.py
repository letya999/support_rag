import os
import json
import yaml
from typing import Any, Dict
from app.nodes.generation.metrics.base import GenerationBaseMetric
from app.logging_config import logger
from app.integrations.llm import get_llm


class AnswerCompleteness(GenerationBaseMetric):
    """LLM-as-judge metric to evaluate answer completeness."""
    
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
    
    def calculate(self, expected: Any, actual: Any, **kwargs) -> float:
        """
        Calculate completeness score.
        
        Args:
            expected: Not used (reference-free)
            actual: The generated answer
            **kwargs: Should contain 'question' and 'context'
            
        Returns:
            float: Completeness score 0-1
        """
        question = kwargs.get("question", "")
        context = kwargs.get("context", "")
        
        if not question or not actual:
            return 0.0
        
        # Format prompt
        prompt = self.prompt_template.format(
            question=question,
            context=context or "No context provided",
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
            score = result.get("completeness_score", 0.0)
            
            # Validate score range
            return max(0.0, min(1.0, float(score)))
            
        except Exception as e:
            logger.error("AnswerCompleteness evaluation failed", extra={"error": str(e)})
            return 0.0
