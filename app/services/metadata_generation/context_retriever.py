from typing import List, Dict, Any
from .models import MetadataConfig

class ContextRetriever:
    """
    Retrieves context (few-shot examples) for LLM validation.
    """
    def __init__(self, config: MetadataConfig):
        self.config = config
        # Placeholder for examples. In a real app, this might load from a DB or vector store
        self.examples = {
            "account_access": [
                {"question": "I forgot my password", "answer": "Click reset password..."},
                {"question": "Cannot login", "answer": "Check your username..."}
            ],
            "billing": [
                {"question": "Where is my invoice?", "answer": "In the billing section..."},
                {"question": "Update credit card", "answer": "Go to payment methods..."}
            ]
        }

    async def get_category_examples(self, category: str) -> List[Dict[str, str]]:
        """
        Retrieve few-shot examples for a given category.
        """
        # Return specific examples if available, otherwise generic or empty
        return self.examples.get(category, [])
