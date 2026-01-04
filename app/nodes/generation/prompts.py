from langchain_core.prompts import ChatPromptTemplate

QA_PROMPT = ChatPromptTemplate.from_template(
    "Ответь на основе контекста пользователю кратко на русском: {docs}\n\nВопрос: {question}"
)

DYNAMIC_QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    ("human", "Контекст:\n{docs}\n\nВопрос: {question}")
])
