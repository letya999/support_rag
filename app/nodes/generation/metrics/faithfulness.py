from app.nodes.retrieval.metrics.base import BaseMetric
from typing import Any, List
from app.integrations.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class Faithfulness(BaseMetric):
    def __init__(self):
        self.llm = get_llm(temperature=0)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert evaluator. Your task is to judge if the provided answer is faithful to the given context. "
                       "The answer is faithful if all the information it contains can be inferred directly from the context. "
                       "If the answer contains information not present in the context, it is not faithful. "
                       "Respond ONLY with a score between 0.0 and 1.0, where 1.0 is perfectly faithful and 0.0 is not faithful at all."),
            ("human", "Context: {context}\n\nAnswer: {answer}\n\nFaithfulness Score:")
        ])
        self.chain = self.prompt | self.llm | StrOutputParser()

    def calculate(self, expected: Any, actual: Any, **kwargs) -> float:
        """
        expected: Not used for faithfulness (usually we check against context)
        actual: The generated answer
        kwargs: Should contain 'context'
        """
        context = kwargs.get("context", "")
        if not context:
            return 0.0
        
        try:
            response = self.chain.invoke({"context": context, "answer": actual})
            return float(response.strip())
        except Exception:
            return 0.0
        
    def aggregate(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

