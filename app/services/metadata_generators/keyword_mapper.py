"""Keyword mapping for automatic category and intent assignment."""

import logging

logger = logging.getLogger(__name__)


class KeywordMapper:
    """Maps keywords to categories and intents."""

    # Category mappings based on keywords
    CATEGORY_KEYWORDS = {
        "Account Access": {
            "password", "login", "reset", "forgot", "sign in", "sign up",
            "account", "auth", "authentication", "2fa", "mfa", "security",
            "unlock", "lockout", "credentials"
        },
        "Order Management": {
            "order", "purchase", "buy", "shipping", "delivery", "track",
            "status", "pending", "cancel", "refund", "return", "exchange",
            "tracking", "shipped", "delivered"
        },
        "Payment & Billing": {
            "payment", "billing", "invoice", "charge", "credit", "debit",
            "payment method", "card", "subscription", "plan", "price",
            "cost", "free trial", "refund"
        },
        "Account Management": {
            "profile", "account", "user", "information", "email", "phone",
            "address", "personal", "update", "edit", "change", "settings",
            "preferences", "notification"
        },
        "Support": {
            "contact", "support", "help", "assist", "issue", "problem",
            "complaint", "feedback", "suggestion", "question", "faq",
            "ticket", "escalat"
        },
        "Technical": {
            "error", "bug", "issue", "crash", "slow", "broken", "not working",
            "failed", "timeout", "connection", "download", "upload", "sync",
            "compatibility", "browser", "device"
        },
        "Features & Usage": {
            "feature", "how", "use", "guide", "tutorial", "manual", "instruction",
            "setup", "configure", "install", "integrate", "api", "plugin"
        },
        "General": {
            "what", "when", "where", "who", "why", "information", "details"
        }
    }

    # Intent mappings
    INTENT_KEYWORDS = {
        "how_to": {"how", "guide", "tutorial", "setup", "configure"},
        "provide_info": {"what", "which", "explain", "describe", "tell me"},
        "check_capability": {"can", "is", "are", "do", "does", "possible", "support"},
        "locate_resource": {"where", "find", "locate", "access", "go to"},
        "troubleshoot": {
            "problem", "issue", "error", "bug", "not working",
            "fail", "crash", "slow"
        },
        "account_action": {
            "reset", "change", "update", "delete", "create",
            "remove", "disable", "enable"
        },
        "contact_support": {"contact", "reach", "speak", "call", "email"},
    }

    @classmethod
    def get_category(cls, text: str) -> str:
        """Get category from text.

        Args:
            text: Text to analyze

        Returns:
            Category name
        """
        text_lower = text.lower()
        words = set(text_lower.split())

        best_category = "General"
        best_score = 0

        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            score = len(words & keywords)
            if score > best_score:
                best_score = score
                best_category = category

        return best_category

    @classmethod
    def get_intent(cls, text: str) -> str:
        """Get intent from text.

        Args:
            text: Text to analyze

        Returns:
            Intent name
        """
        text_lower = text.lower()
        words = set(text_lower.split())

        best_intent = "provide_info"
        best_score = 0

        for intent, keywords in cls.INTENT_KEYWORDS.items():
            score = len(words & keywords)
            if score > best_score:
                best_score = score
                best_intent = intent

        return best_intent

    @classmethod
    def get_handoff_required(cls, text: str) -> bool:
        """Determine if customer handoff is required.

        Args:
            text: Answer text to check

        Returns:
            True if handoff required
        """
        handoff_indicators = {
            "contact", "reach", "speak", "call", "email", "agent",
            "representative", "support", "team", "ticket",
            "escalate", "escalation", "supervisor", "manager"
        }

        text_lower = text.lower()
        words = set(text_lower.split())

        return len(words & handoff_indicators) > 0

    @classmethod
    def get_confidence_threshold(cls, text: str) -> float:
        """Get recommended confidence threshold.

        Args:
            text: Text to analyze

        Returns:
            Confidence threshold (0.0-1.0)
        """
        # If text is very clear and contains instructions, higher confidence
        if "step" in text.lower() or "follow" in text.lower():
            return 0.9

        # If text has conditionals, lower confidence
        conditionals = {"if", "depends", "depending", "unless", "except"}
        text_lower = text.lower()
        if any(cond in text_lower for cond in conditionals):
            return 0.7

        # Default
        return 0.8

    @classmethod
    def generate_clarifying_questions(cls, question: str, answer: str) -> list:
        """Generate clarifying questions if needed.

        Args:
            question: Question text
            answer: Answer text

        Returns:
            List of clarifying questions
        """
        clarifying = []

        # If answer has conditionals, ask clarifying questions
        text_combined = (question + " " + answer).lower()

        if "email" in text_combined and "account" in text_combined:
            clarifying.append("Do you have access to the email address associated with your account?")

        if "account" in text_combined:
            clarifying.append("Is this a personal or business account?")

        if "password" in text_combined:
            clarifying.append("Are you trying to reset your password?")

        if "free" in text_combined or "trial" in text_combined:
            clarifying.append("Are you interested in the free trial?")

        if "premium" in text_combined or "plan" in text_combined:
            clarifying.append("Which plan are you currently using?")

        return clarifying
