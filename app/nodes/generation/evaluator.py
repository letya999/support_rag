from typing import Dict, Any, Optional, List
from app.nodes.base_node import BaseEvaluator
from app.nodes.generation.metrics import Faithfulness, Relevancy
from app.nodes.generation.node import generate_answer_simple
from app.nodes.retrieval.search import retrieve_context

class GenerationEvaluator(BaseEvaluator):
    def __init__(self):
        super().__init__()
        self.faithfulness = Faithfulness()
        self.relevancy = Relevancy()
        self.metrics = [self.faithfulness, self.relevancy]
        
    def calculate_metrics(self, question: str, context: str, answer: str) -> Dict[str, float]:
        """
        Calculate metrics for a generated answer.
        """
        return {
            "faithfulness": self.faithfulness.calculate(None, answer, context=context),
            "relevancy": self.relevancy.calculate(None, answer, question=question)
        }

    async def evaluate_single(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Run retrieval, then generate an answer and evaluate it.
        """
        # 1. Retrieve
        retrieval_output = await retrieve_context(question, top_k=top_k)
        docs = retrieval_output.docs
        
        # 2. Generate
        answer = await generate_answer_simple(question, docs)
        
        # 3. Metrics
        metrics = self.calculate_metrics(question, "\n\n".join(docs), answer)
        
        return {
            "answer": answer,
            "docs": docs,
            "metrics": metrics
        }

evaluator = GenerationEvaluator()


