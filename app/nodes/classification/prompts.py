"""Intent and category definitions for zero-shot classification."""

# Supported intents
INTENTS = [
    "faq",              # General question
    "complaint",        # User complaint
    "suggestion",       # User suggestion/feature request
    "technical",        # Technical issue
    "billing",          # Billing related
    "account",          # Account management
]

# Supported categories
CATEGORIES = [
    "billing",          # Billing & payments
    "shipping",         # Shipping & delivery
    "account",          # Account & authentication
    "product",          # Product info
    "returns",          # Returns & refunds
    "technical",        # Technical support
    "general",          # General inquiry
]

# Optional: Hint phrases for improving classification (for debugging/tuning)
INTENT_HINTS = {
    "faq": ["how", "what", "can", "do you", "where", "when", "why"],
    "complaint": ["bad", "wrong", "broken", "not working", "issue", "problem"],
    "suggestion": ["suggest", "feature", "idea", "improvement", "better"],
    "technical": ["error", "bug", "crash", "doesn't work", "failed"],
    "billing": ["price", "cost", "charge", "payment", "invoice"],
    "account": ["account", "login", "password", "profile", "access"],
}

CATEGORY_HINTS = {
    "billing": ["payment", "invoice", "price", "cost", "refund", "charge"],
    "shipping": ["delivery", "ship", "package", "tracking", "order", "address"],
    "account": ["login", "password", "account", "profile", "access", "username"],
    "product": ["product", "item", "feature", "specification", "model"],
    "returns": ["return", "refund", "exchange", "warranty", "damaged"],
    "technical": ["error", "bug", "crash", "not working", "issue"],
    "general": ["information", "help", "support", "question"],
}
