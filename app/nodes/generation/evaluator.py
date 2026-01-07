from typing import Dict, Any, Optional, List
from app.nodes.base_node import BaseEvaluator
from app.nodes.generation.metrics import Faithfulness, AnswerRelevancy, AnswerCompleteness, ConversationalAppropriateness
from app.nodes.generation.node import generate_answer_simple
from app.nodes.retrieval.search import retrieve_context

class GenerationEvaluator(BaseEvaluator):
    def __init__(self):
        super().__init__()
        self.faithfulness = Faithfulness()
        self.answer_relevancy = AnswerRelevancy()
        self.answer_completeness = AnswerCompleteness()
        self.conversational_appropriateness = ConversationalAppropriateness()
        self.metrics = [
            self.faithfulness, 
            self.answer_relevancy, 
            self.answer_completeness,
            self.conversational_appropriateness
        ]
        
    def calculate_metrics(self, state: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate all generation metrics from state.
        
        Args:
            state: Pipeline state dictionary containing:
                - question: str
                - answer: str
                - docs: List[str]
                - conversation_history: List (optional)
                - sentiment: Dict (optional)
                
        Returns:
            Dict[str, float]: Metric scores
        """
        question = state.get("question", "")
        answer = state.get("answer", "")
        docs = state.get("docs", [])
        context = "\n\n".join(docs) if docs else ""
        conversation_history = state.get("conversation_history", [])
        sentiment = state.get("sentiment", {})
        
        if not answer:
            return {
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "answer_completeness": 0.0,
                "conversational_appropriateness": 0.0
            }
        
        return {
            "faithfulness": self.faithfulness.calculate(None, answer, context=context),
            "answer_relevancy": self.answer_relevancy.calculate(None, answer, question=question),
            "answer_completeness": self.answer_completeness.calculate(
                None, answer, question=question, context=context
            ),
            "conversational_appropriateness": self.conversational_appropriateness.calculate(
                None, answer, 
                question=question,
                conversation_history=conversation_history,
                sentiment=sentiment
            )
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
        state = {
            "question": question,
            "answer": answer,
            "docs": docs,
            "conversation_history": [],
            "sentiment": {"label": "neutral", "score": 0.0}
        }
        metrics = self.calculate_metrics(state)
        
        return {
            "answer": answer,
            "docs": docs,
            "metrics": metrics
        }

evaluator = GenerationEvaluator()
