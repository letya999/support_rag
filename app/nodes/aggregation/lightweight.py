import re
from typing import Dict, Any, List
from app.pipeline.state import State
from app.pipeline.config_proxy import conversation_config

def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extracts entities using regex from text.
    """
    entities = {
        "emails": [],
        "phones": [],
        "order_ids": [],
        "dates": []
    }
    
    # Email
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    entities["emails"] = re.findall(email_pattern, text)
    
    # Phone (RU/International simplistic)
    phone_pattern = r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
    entities["phones"] = re.findall(phone_pattern, text)
    
    # Order IDs (e.g., #12345, ORD-12345)
    order_pattern = r'#\d+|ORD-\d+|ORDER-\d+'
    entities["order_ids"] = re.findall(order_pattern, text, re.IGNORECASE)
    
    # Dates (DD.MM.YYYY or YYYY-MM-DD)
    date_pattern = r'\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}'
    entities["dates"] = re.findall(date_pattern, text)
    
    return {k: list(set(v)) for k, v in entities.items() if v}

def is_context_dependent(text: str) -> bool:
    """
    Checks if the text likely refers to previous context.
    """
    context_markers = [
        "о нем", "про него", "с ним", "это", "эта", "этот", 
        "it", "that", "this", "status", "статус", 
        "предыдущ", "прошл"
    ]
    text_lower = text.lower()
    return any(marker in text_lower for marker in context_markers)

def lightweight_aggregation_node(state: State) -> Dict[str, Any]:
    """
    Aggregates conversation history and extracts entities without LLM.
    """
    question = state.get("question", "")
    history = state.get("conversation_history", []) or []
    
    # 1. Filter User Messages
    max_msgs = conversation_config.aggregation_max_messages
    user_msgs = []
    for msg in history:
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", "")
            
        if role == "user":
            user_msgs.append(content)
            
    user_msgs = user_msgs[-max_msgs:]
    
    # Add current question if not already in history (it might be or might not, depends on when we add it)
    # Usually history comes from DB/Session, logic assumes 'question' is the *new* input.
    # We should consider 'question' as part of the context.
    
    current_context_text = " ".join(user_msgs + [question])
    
    # 2. Extract Entities
    entities = extract_entities(current_context_text)
    
    # 3. Build Aggregated Query
    aggregated_query = question
    
    # If the question seems context-dependent or short, enrich it
    if is_context_dependent(question) or len(question.split()) < 3:
        # Append found entities to the query to make it standalone
        extras = []
        for k, vals in entities.items():
            for v in vals:
                extras.append(v)
        
        # Fallback: If no explicit entities found (regex), try to extract keywords from the last User message
        # This fixes cases like "My internet is broken" -> "Fix it" (where "internet" is not a regex entity)
        if not extras and user_msgs:
            last_user_msg = user_msgs[-1]
            keywords = extract_keywords(last_user_msg)
            if keywords:
                extras.extend(keywords)
        
        if extras:
            # Deduplicate
            extras = list(set(extras))
            aggregated_query = f"{question} (Context: {', '.join(extras)})"
            
    # If we have a lot of user history but no specific entities, we might just leave it 
    # or append the previous user message if it was very recent. 
    # For now, let's keep it simple: enrich with entities.
    
    return {
        "aggregated_query": aggregated_query,
        "extracted_entities": entities
    }

def extract_keywords(text: str) -> List[str]:
    """
    Extracts significant keywords (nouns/proper nouns approximation) by filtering stopwords.
    Simple 'Bag of Words' approach using a lightweight stopword list.
    """
    # Basic Russian + English stopwords
    STOPWORDS = {
        'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или', 'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничего', 'ей', 'может', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'была', 'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет', 'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем', 'ним', 'здесь', 'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'сейчас', 'были', 'куда', 'зачем', 'всех', 'никогда', 'можно', 'при', 'наконец', 'два', 'об', 'другой', 'хоть', 'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего', 'них', 'какая', 'много', 'разве', 'три', 'эту', 'моя', 'впрочем', 'хорошо', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть', 'том', 'нельзя', 'такой', 'им', 'более', 'всегда', 'конечно', 'всю', 'между', 'привет', 'здравствуйте', 'пожалуйста', 'спасибо',
        'the', 'is', 'at', 'which', 'on', 'and', 'a', 'an', 'in', 'to', 'of', 'for', 'it', 'that', 'this', 'my', 'his', 'her', 'our', 'their', 'with', 'as', 'be', 'have', 'do', 'will', 'can', 'hello', 'hi', 'please', 'thanks', 'help'
    }
    
    # normalize
    words = re.findall(r'\w+', text.lower())
    
    # Filter
    keywords = [w for w in words if w not in STOPWORDS and len(w) > 2 and not w.isdigit()]
    
    # Limit to top 5 unique to avoid noise
    return list(set(keywords))[:5]
