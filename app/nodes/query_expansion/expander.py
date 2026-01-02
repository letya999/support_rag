from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import CommaSeparatedListOutputParser
from app.integrations.llm import get_llm
from app.observability.tracing import observe

EXPANSION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a search query expansion assistant. Your task is to generate 3 alternative versions of the user's question to improve search retrieval. Provide only the expanded queries, separated by commas."),
    ("user", "{question}")
])

class QueryExpander:
    def __init__(self):
        self.llm = get_llm(temperature=0.7) # Higher temperature for variety
        self.output_parser = CommaSeparatedListOutputParser()
        self.chain = EXPANSION_PROMPT | self.llm | self.output_parser

    @observe(as_type="span")
    async def expand(self, question: str) -> List[str]:
        """
        Generate alternative queries using LLM.
        """
        expanded_queries = await self.chain.ainvoke({"question": question})
        # Add original question to the list and deduplicate
        all_queries = list(set([question] + [q.strip() for q in expanded_queries if q.strip()]))
        return all_queries
