
import re

QUESTION_PATTERNS = [
    r'\?$',                          # Ends with ?
    r'^(what|how|why|when|where|who|which|can|do|does|did|is|are|will|would|could|please|pls)\b',
    r'^(как|почему|когда|где|кто|какой|можно|ли|пожалуйста|плиз)\b',
    r'\b(tell me|explain|describe|show|help)\b',
    r'\b(расскажи|объясни|покажи|помоги)\b',
    r'\b(about|про|о|об)\b.*\??\s*$',  # Question about something
]

def is_question(text: str) -> bool:
    """
    Determine if the text is a question based on regex patterns.
    """
    if not text:
        return False
        
    text_lower = text.lower().strip()
    
    for pattern in QUESTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False
