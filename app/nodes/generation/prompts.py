from langchain_core.prompts import ChatPromptTemplate

QA_PROMPT = ChatPromptTemplate.from_template(
    "Ответь на основе контекста пользователю кратко на русском: {docs}\n\nВопрос: {question}"
)
