import os
import yaml
from typing import Any
from app.nodes.generation.metrics.base import GenerationBaseMetric
from app.integrations.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


class Faithfulness(GenerationBaseMetric):
    """LLM-as-judge metric to evaluate answer faithfulness to context."""
    
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
            temperature=self.config.get("temperature", 0.0)
        )
        
        # Build chain
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert evaluator. Your task is to judge if the provided answer is faithful to the given context."),
            ("human", self.prompt_template)
        ])
        self.chain = self.prompt | self.llm | StrOutputParser()
    
    def calculate(self, expected: Any, actual: Any, **kwargs) -> float:
        """
        Calculate faithfulness score.
        
        Args:
            expected: Not used (reference-free)
            actual: The generated answer
            **kwargs: Should contain 'context'
            
        Returns:
            float: Faithfulness score 0-1
        """
        context = kwargs.get("context", "")
        if not context or not actual:
            return 0.0
        
        try:
            response = self.chain.invoke({
                "context": context,
                "answer": actual
            })
            
            # Extract score from response
            score_str = response.strip()
            # Remove any potential trailing text
            score_str = score_str.split()[0] if score_str else "0.0"
            score = float(score_str)
            
            # Validate range
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            print(f"⚠️ Faithfulness evaluation failed: {e}")
            return 0.0
