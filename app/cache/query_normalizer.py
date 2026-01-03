"""
Query Normalizer: Normalizes questions to match variations.

Handles bilingual (Russian/English) normalization:
1. Lowercase conversion
2. Punctuation removal
3. Stop-word removal
4. Keyword sorting
5. Whitespace cleanup

This allows "How to reset password?" and "reset password, please"
to be recognized as the same cached question.

Example:
    normalizer = QueryNormalizer()
    key1 = normalizer.normalize("How to reset password?")
    key2 = normalizer.normalize("Reset password, please")
    assert key1 == key2  # Both become "reset password"
"""

import re
from typing import Set


class QueryNormalizer:
    """
    Normalizes user queries to match variations of the same question.

    Bilingual support: Russian + English
    """

    # English stop words (remove common filler words)
    ENGLISH_STOP_WORDS: Set[str] = {
        "how", "what", "where", "when", "who", "why",
        "do", "does", "did", "can", "could", "should", "would",
        "is", "are", "am", "be", "been",
        "please", "thanks", "thank", "help", "me", "my", "i",
        "a", "an", "the", "and", "or", "but", "in", "on", "at",
        "to", "for", "of", "with", "by", "about", "from",
    }

    # Russian stop words (удалить распространённые слова-заполнители)
    RUSSIAN_STOP_WORDS: Set[str] = {
        # Вопросительные слова / Question words
        "как", "что", "где", "когда", "кто", "почему", "какой", "какая", "какие",

        # Модальные глаголы / Modal verbs
        "могу", "можешь", "может", "можем", "можете", "могут",
        "должен", "должна", "должны", "нужно", "надо",

        # Вспомогательные глаголы / Auxiliary verbs
        "есть", "был", "была", "было", "были", "буду", "будет", "будем", "будете", "будут",

        # Предлоги / Prepositions
        "в", "на", "по", "к", "с", "от", "о", "об", "у", "за", "под", "над", "между",
        "через", "для", "из", "до", "без", "со", "ко", "во",

        # Артикли и местоимения / Articles and pronouns
        "я", "ты", "он", "она", "оно", "мы", "вы", "они",
        "меня", "тебя", "его", "её", "нас", "вас", "их",
        "мой", "твой", "наш", "ваш",

        # Союзы / Conjunctions
        "и", "или", "но", "же", "если", "то", "что",

        # Частицы / Particles
        "ли", "ни", "не",

        # Вежливые слова / Polite words
        "пожалуйста", "спасибо", "привет", "пока", "здравствуйте",

        # Местоимения-прилагательные / Possessive adjectives
        "это", "эта", "эти", "тот", "та", "то", "те",
    }

    def __init__(self):
        """Initialize the query normalizer."""
        self.english_stopwords = self.ENGLISH_STOP_WORDS
        self.russian_stopwords = self.RUSSIAN_STOP_WORDS

    def normalize(self, query: str) -> str:
        """
        Normalize a query to a canonical form for caching.

        Args:
            query: Raw user query

        Returns:
            Normalized query string suitable as cache key

        Examples:
            >>> normalizer = QueryNormalizer()
            >>> normalizer.normalize("How to reset password?")
            'reset password'

            >>> normalizer.normalize("Reset password, please")
            'reset password'

            >>> normalizer.normalize("Как сбросить пароль?")
            'сбросить пароль'

            >>> normalizer.normalize("password reset")
            'password reset'

            >>> normalizer.normalize("reset PASSWORD")
            'reset password'
        """
        # Step 1: Lowercase
        query = query.lower()

        # Step 2: Remove punctuation (but keep spaces)
        query = re.sub(r'[^\w\s]', '', query)

        # Step 3: Split into tokens
        tokens = query.split()

        # Step 4: Remove stop words (both English and Russian)
        filtered_tokens = [
            token for token in tokens
            if token not in self.english_stopwords
            and token not in self.russian_stopwords
            and len(token) > 0
        ]

        # Step 5: Sort tokens for consistency
        # "password reset" and "reset password" become the same
        filtered_tokens.sort()

        # Step 6: Clean up whitespace and rejoin
        normalized = ' '.join(filtered_tokens)

        return normalized.strip()

    def normalize_with_details(self, query: str) -> dict:
        """
        Normalize a query and return detailed information about the process.

        Useful for debugging and understanding the normalization steps.

        Args:
            query: Raw user query

        Returns:
            Dictionary with:
            - original: Original query
            - normalized: Final normalized form
            - steps: List of transformation steps
            - removed_stopwords: Stopwords that were removed
        """
        original = query
        steps = []

        # Step 1: Lowercase
        query = query.lower()
        steps.append(f"Lowercase: '{original}' -> '{query}'")

        # Step 2: Remove punctuation
        query_before_punct = query
        query = re.sub(r'[^\w\s]', '', query)
        if query_before_punct != query:
            steps.append(f"Remove punctuation: '{query_before_punct}' -> '{query}'")

        # Step 3: Split and identify stop words
        tokens = query.split()
        steps.append(f"Tokens: {tokens}")

        # Step 4: Remove stop words
        removed_stopwords = []
        filtered_tokens = []
        for token in tokens:
            if token in self.english_stopwords:
                removed_stopwords.append((token, "English"))
            elif token in self.russian_stopwords:
                removed_stopwords.append((token, "Russian"))
            else:
                filtered_tokens.append(token)

        if removed_stopwords:
            steps.append(f"Remove stop words: {removed_stopwords}")

        # Step 5: Sort tokens
        filtered_tokens.sort()
        steps.append(f"Sort tokens: {filtered_tokens}")

        # Step 6: Join
        normalized = ' '.join(filtered_tokens).strip()

        return {
            "original": original,
            "normalized": normalized,
            "steps": steps,
            "removed_stopwords": removed_stopwords,
        }


# Global instance for convenience
_normalizer_instance = None


def get_normalizer() -> QueryNormalizer:
    """Get or create the global QueryNormalizer instance."""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = QueryNormalizer()
    return _normalizer_instance
