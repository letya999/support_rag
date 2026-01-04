from app.nodes.generation.metrics.base import GenerationBaseMetric
from typing import Any, List
from app.integrations.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class Relevancy(GenerationBaseMetric):
    def __init__(self):
        self.llm = get_llm(temperature=0)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert evaluator. Your task is to judge if the provided answer is relevant to the question asked. "
                       "A relevant answer addresses the question directly and providing accurate information based on the question's intent. "
                       "Respond ONLY with a score between 0.0 and 1.0, where 1.0 is perfectly relevant and 0.0 is not relevant at all."),
            ("human", "Question: {question}\n\nAnswer: {answer}\n\nRelevancy Score:")
        ])
        self.chain = self.prompt | self.llm | StrOutputParser()

    def calculate(self, expected: Any, actual: Any, **kwargs) -> float:
        """
        expected: Not used for relevancy (usually we check against question)
        actual: The generated answer
        kwargs: Should contain 'question'
        """
        question = kwargs.get("question", "")
        if not question:
            return 0.0
        
        try:
            response = self.chain.invoke({"question": question, "answer": actual})
            return float(response.strip())
        except Exception:
            return 0.0

