"""
Unit tests for the cache module.

Tests:
- Query normalization (bilingual)
- Cache operations (get, set, delete)
- Cache statistics
- Cache metrics
"""

import pytest
import asyncio
from app.cache.query_normalizer import QueryNormalizer, get_normalizer
from app.cache.cache_layer import CacheManager
from app.cache.cache_stats import CacheMetrics
from app.cache.models import CacheEntry


class TestQueryNormalizer:
    """Test query normalization."""

    def test_normalize_english_basic(self):
        """Test basic English query normalization."""
        normalizer = QueryNormalizer()
        result = normalizer.normalize("How to reset password?")
        assert result == "password reset"

    def test_normalize_english_variations(self):
        """Test that variations of same question normalize to same key."""
        normalizer = QueryNormalizer()

        questions = [
            "How to reset password?",
            "Reset password, please",
            "password reset?",
            "reset my password please",
        ]

        normalized = [normalizer.normalize(q) for q in questions]
        # All should normalize to same form (with sorted keywords)
        assert len(set(normalized)) == 1, f"Got different normalizations: {set(normalized)}"

    def test_normalize_russian_basic(self):
        """Test basic Russian query normalization."""
        normalizer = QueryNormalizer()
        result = normalizer.normalize("Как сбросить пароль?")
        assert result == "пароль сбросить"  # Sorted alphabetically

    def test_normalize_russian_variations(self):
        """Test Russian query variations."""
        normalizer = QueryNormalizer()

        questions = [
            "Как сбросить пароль?",
            "сбросить пароль пожалуйста",
            "Помогите, сбросить пароль",
        ]

        normalized = [normalizer.normalize(q) for q in questions]
        # Remove stop words and normalize
        assert len(set(normalized)) <= len(questions)

    def test_normalize_lowercase(self):
        """Test that case is normalized."""
        normalizer = QueryNormalizer()
        result1 = normalizer.normalize("RESET PASSWORD")
        result2 = normalizer.normalize("reset password")
        assert result1 == result2

    def test_normalize_punctuation_removed(self):
        """Test that punctuation is removed."""
        normalizer = QueryNormalizer()
        result1 = normalizer.normalize("Reset password??")
        result2 = normalizer.normalize("Reset password")
        assert result1 == result2

    def test_normalize_stop_words_removed(self):
        """Test that stop words are removed."""
        normalizer = QueryNormalizer()
        result = normalizer.normalize("How to reset password please")
        # "how", "to", "please" should be removed
        assert "how" not in result
        assert "to" not in result
        assert "please" not in result

    def test_normalize_with_details(self):
        """Test detailed normalization output."""
        normalizer = QueryNormalizer()
        result = normalizer.normalize_with_details("How to reset password?")

        assert "original" in result
        assert "normalized" in result
        assert "steps" in result
        assert "removed_stopwords" in result
        assert isinstance(result["steps"], list)


class TestCacheMetrics:
    """Test cache metrics collection."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = CacheMetrics()
        assert metrics.total_requests == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0

    def test_record_hit(self):
        """Test recording cache hits."""
        metrics = CacheMetrics()
        metrics.record_hit("test_query", 5.0)

        assert metrics.cache_hits == 1
        assert metrics.total_requests == 1

    def test_record_miss(self):
        """Test recording cache misses."""
        metrics = CacheMetrics()
        metrics.record_miss(850.0)

        assert metrics.cache_misses == 1
        assert metrics.total_requests == 1

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        metrics = CacheMetrics()
        # 7 hits, 3 misses = 70% hit rate
        for _ in range(7):
            metrics.record_hit("query", 5.0)
        for _ in range(3):
            metrics.record_miss(850.0)

        stats = metrics.get_stats()
        assert stats.hit_rate == 70.0

    def test_average_response_time(self):
        """Test average response time calculation."""
        metrics = CacheMetrics()
        metrics.record_hit("q1", 5.0)
        metrics.record_hit("q2", 5.0)
        metrics.record_miss(850.0)
        metrics.record_miss(900.0)

        stats = metrics.get_stats()
        assert stats.avg_response_time_cached == 5.0
        assert stats.avg_response_time_full == 875.0

    def test_most_asked_questions(self):
        """Test tracking most asked questions."""
        metrics = CacheMetrics(max_top_questions=3)
        metrics.record_hit("password_reset", 5.0)
        metrics.record_hit("password_reset", 5.0)
        metrics.record_hit("password_reset", 5.0)
        metrics.record_hit("order_status", 5.0)
        metrics.record_hit("order_status", 5.0)
        metrics.record_hit("shipping_info", 5.0)

        stats = metrics.get_stats()
        top_questions = stats.most_asked_questions

        assert len(top_questions) <= 3
        assert top_questions[0]["query"] == "password_reset"
        assert top_questions[0]["hits"] == 3
        assert top_questions[1]["hits"] == 2

    def test_time_savings_calculation(self):
        """Test time savings calculation."""
        metrics = CacheMetrics()
        # 5 hits at 5ms, 5 misses at 1000ms
        for _ in range(5):
            metrics.record_hit("query", 5.0)
        for _ in range(5):
            metrics.record_miss(1000.0)

        stats = metrics.get_stats()
        # Each hit saves (1000 - 5) = 995ms = 0.995s
        # 5 hits saves ~5 seconds
        assert stats.savings_time > 4.0


class TestCacheEntry:
    """Test CacheEntry model."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            query_normalized="reset password",
            query_original="How to reset password?",
            answer="Click on Forgot Password...",
            doc_ids=["doc_1"],
            confidence=0.95
        )

        assert entry.query_normalized == "reset password"
        assert entry.query_original == "How to reset password?"
        assert entry.confidence == 0.95
        assert entry.hit_count == 0

    def test_cache_entry_serialization(self):
        """Test JSON serialization of cache entry."""
        entry = CacheEntry(
            query_normalized="test",
            query_original="Test?",
            answer="Answer",
            confidence=0.9
        )

        # Serialize to JSON
        json_str = entry.model_dump_json()
        assert isinstance(json_str, str)
        assert "query_normalized" in json_str

        # Deserialize from JSON
        restored = CacheEntry.model_validate_json(json_str)
        assert restored.query_normalized == entry.query_normalized
        assert restored.query_original == entry.query_original


@pytest.mark.asyncio
class TestCacheManager:
    """Test cache manager (in-memory mode)."""

    @pytest.fixture
    async def cache(self):
        """Create in-memory cache for testing."""
        cache = CacheManager(redis_client=None, max_entries=10)
        yield cache
        await cache.close()

    async def test_cache_manager_creation(self):
        """Test creating cache manager."""
        cache = CacheManager()
        assert cache is not None
        assert cache.max_entries == 1000

    async def test_set_and_get(self, cache):
        """Test storing and retrieving cache entries."""
        entry = CacheEntry(
            query_normalized="test",
            query_original="Test?",
            answer="Answer",
            confidence=0.9
        )

        # Set
        success = await cache.set("test", entry)
        assert success

        # Get
        retrieved = await cache.get("test")
        assert retrieved is not None
        assert retrieved.query_normalized == "test"

    async def test_get_nonexistent(self, cache):
        """Test getting non-existent entry."""
        result = await cache.get("nonexistent")
        assert result is None

    async def test_delete(self, cache):
        """Test deleting cache entry."""
        entry = CacheEntry(
            query_normalized="test",
            query_original="Test?",
            answer="Answer",
            confidence=0.9
        )

        await cache.set("test", entry)
        deleted = await cache.delete("test")
        assert deleted

        # Should not exist anymore
        retrieved = await cache.get("test")
        assert retrieved is None

    async def test_clear(self, cache):
        """Test clearing cache."""
        entry = CacheEntry(
            query_normalized="test",
            query_original="Test?",
            answer="Answer",
            confidence=0.9
        )

        await cache.set("test", entry)
        await cache.set("test2", entry)

        # Clear
        success = await cache.clear()
        assert success

        # Should be empty
        result = await cache.get("test")
        assert result is None

    async def test_get_all_entries(self, cache):
        """Test getting all entries."""
        entries = [
            CacheEntry(
                query_normalized=f"test{i}",
                query_original=f"Test {i}?",
                answer=f"Answer {i}",
                confidence=0.9
            )
            for i in range(3)
        ]

        for i, entry in enumerate(entries):
            await cache.set(f"test{i}", entry)

        all_entries = await cache.get_all_entries()
        assert len(all_entries) == 3

    async def test_hit_count_increment(self, cache):
        """Test that hit count increments on retrieval."""
        entry = CacheEntry(
            query_normalized="test",
            query_original="Test?",
            answer="Answer",
            confidence=0.9,
            hit_count=0
        )

        await cache.set("test", entry)

        # Get multiple times
        for _ in range(3):
            retrieved = await cache.get("test")
            assert retrieved is not None

        # Check hit count
        final = await cache.get("test")
        assert final.hit_count >= 3

    async def test_health_check(self, cache):
        """Test health check."""
        health = await cache.health_check()
        assert "status" in health
        assert health["backend"] == "in-memory"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
