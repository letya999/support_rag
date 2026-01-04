from langchain_core.prompts import ChatPromptTemplate
import os

def _load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

QA_PROMPT = ChatPromptTemplate.from_template(_load_prompt("prompt_qa_simple.txt"))

DYNAMIC_QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    ("human", _load_prompt("prompt_qa_dynamic_human.txt"))
])
