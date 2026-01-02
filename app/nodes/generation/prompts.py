from langchain_core.prompts import ChatPromptTemplate

QA_PROMPT = ChatPromptTemplate.from_template(
    "Ответь на основе контекста: {docs}\n\nВопрос: {question}"
)
