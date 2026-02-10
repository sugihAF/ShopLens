"""Integration tests for the review pipeline functions."""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.product import Product
from app.models.reviewer import Reviewer, Platform
from app.models.review import Review, ReviewType, ProcessingStatus


@pytest.fixture
def mock_gemini_response():
    """Create a mock Gemini response object."""
    def _make_response(text: str):
        mock = MagicMock()
        mock.text = text
        mock.candidates = [MagicMock()]
        mock.candidates[0].grounding_metadata = None
        return mock
    return _make_response


@pytest.fixture
def youtube_review_json():
    return json.dumps({
        "video_title": "Samsung Galaxy S25 Ultra Review",
        "channel_name": "MKBHD",
        "reviewer_description": "Popular tech reviewer",
        "detailed_review": "This is a comprehensive review of the Samsung Galaxy S25 Ultra. The phone features an excellent display.",
        "pros": ["Great display", "Fast performance"],
        "cons": ["Expensive", "Heavy"],
        "verdict": "A solid flagship phone worth considering.",
        "product_name": "Samsung Galaxy S25 Ultra",
        "product_brand": "Samsung",
        "product_category": "smartphones"
    })


@pytest.fixture
def blog_review_json():
    return json.dumps({
        "article_title": "Samsung Galaxy S25 Ultra Review: A Worthy Upgrade",
        "publication_name": "The Verge",
        "author": "Dieter Bohn",
        "detailed_review": "The Verge's take on the Samsung Galaxy S25 Ultra. It's a notable improvement.",
        "pros": ["Improved camera", "Better battery"],
        "cons": ["Same design", "Still expensive"],
        "verdict": "A great phone if you're due for an upgrade.",
        "product_name": "Samsung Galaxy S25 Ultra",
        "product_brand": "Samsung",
        "product_category": "smartphones"
    })


@pytest.fixture
def mock_firecrawl_youtube_results():
    return [
        {"url": "https://www.youtube.com/watch?v=abc12345678", "title": "Galaxy S25 Review", "description": "Review"},
        {"url": "https://www.youtube.com/watch?v=def12345678", "title": "Galaxy S25 Hands On", "description": "Hands on"},
        {"url": "https://www.youtube.com/watch?v=ghi12345678", "title": "Galaxy S25 Camera Test", "description": "Camera"},
    ]


@pytest.fixture
def mock_firecrawl_blog_results():
    return [
        {"url": "https://www.theverge.com/review/galaxy-s25", "title": "Galaxy S25 Review", "description": "Review"},
        {"url": "https://www.cnet.com/review/galaxy-s25", "title": "Galaxy S25 Review", "description": "Review"},
    ]


class TestCheckProductCache:
    """Test check_product_cache function."""

    @pytest.mark.asyncio
    @patch("app.functions.review_tools.cache")
    async def test_cache_miss_returns_not_found(self, mock_cache, db_session):
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.hash_key = MagicMock(return_value="product_cache:test")

        from app.functions.review_tools import check_product_cache
        result = await check_product_cache(db_session, {"product_name": "NonExistent Product XYZ"})
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    @patch("app.functions.review_tools.cache")
    async def test_redis_cache_hit(self, mock_cache, db_session):
        cached_data = {"status": "found", "product": {"name": "Test"}, "reviews": []}
        mock_cache.get = AsyncMock(return_value=cached_data)
        mock_cache.hash_key = MagicMock(return_value="product_cache:test")

        from app.functions.review_tools import check_product_cache
        result = await check_product_cache(db_session, {"product_name": "Test"})
        assert result["status"] == "found"


class TestSearchYoutubeReviews:
    """Test search_youtube_reviews function."""

    @pytest.mark.asyncio
    @patch("app.functions.review_tools._firecrawl_search")
    async def test_returns_youtube_urls(self, mock_search, db_session, mock_firecrawl_youtube_results):
        mock_search.return_value = mock_firecrawl_youtube_results

        from app.functions.review_tools import search_youtube_reviews
        result = await search_youtube_reviews(db_session, {
            "product_name": "Samsung Galaxy S25",
            "limit": 3
        })

        assert result["status"] == "success"
        assert len(result["urls"]) == 3
        assert all("youtube.com" in url for url in result["urls"])

    @pytest.mark.asyncio
    @patch("app.functions.review_tools._firecrawl_search")
    async def test_returns_no_results(self, mock_search, db_session):
        mock_search.return_value = []

        from app.functions.review_tools import search_youtube_reviews
        result = await search_youtube_reviews(db_session, {"product_name": "NonExistent"})
        assert result["status"] == "no_results"
        assert result["urls"] == []


class TestIngestReviewsBatch:
    """Test batch ingestion function."""

    @pytest.mark.asyncio
    @patch("app.functions.review_tools.embedding_service")
    @patch("app.functions.review_tools._call_gemini_with_retry")
    @patch("app.functions.review_tools._get_gemini_client")
    async def test_parallel_ingestion(
        self, mock_client, mock_gemini_call, mock_embedding,
        db_session, youtube_review_json, blog_review_json, mock_gemini_response
    ):
        """Test that batch ingestion processes URLs in parallel."""
        mock_client.return_value = MagicMock()
        mock_embedding.store_review_embedding = AsyncMock(return_value=True)

        # Alternate between youtube and blog responses
        call_count = 0
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return mock_gemini_response(youtube_review_json)
            return mock_gemini_response(blog_review_json)

        mock_gemini_call.side_effect = side_effect

        from app.functions.review_tools import ingest_reviews_batch
        result = await ingest_reviews_batch(db_session, {
            "product_name": "Samsung Galaxy S25 Ultra",
            "youtube_urls": [
                "https://www.youtube.com/watch?v=test1234567",
                "https://www.youtube.com/watch?v=test2234567",
            ],
            "blog_urls": [
                "https://www.theverge.com/review/test",
            ]
        })

        assert result["total"] == 3
        assert result["succeeded"] >= 1

    @pytest.mark.asyncio
    async def test_batch_requires_product_name(self, db_session):
        from app.functions.review_tools import ingest_reviews_batch
        result = await ingest_reviews_batch(db_session, {
            "youtube_urls": ["https://www.youtube.com/watch?v=test1234567"]
        })
        assert "error" in result

    @pytest.mark.asyncio
    async def test_batch_requires_urls(self, db_session):
        from app.functions.review_tools import ingest_reviews_batch
        result = await ingest_reviews_batch(db_session, {
            "product_name": "Test Product"
        })
        assert "error" in result


class TestGetReviewsSummary:
    """Test get_reviews_summary with pre-populated data."""

    @pytest.mark.asyncio
    @patch("app.functions.review_tools.cache")
    @patch("app.functions.review_tools._call_gemini_with_timeout")
    @patch("app.functions.review_tools._get_gemini_client")
    async def test_summary_generation(
        self, mock_client, mock_gemini_call, mock_cache,
        db_session, mock_gemini_response
    ):
        """Test summary generation with pre-populated reviews."""
        mock_client.return_value = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.hash_key = MagicMock(return_value="summary:test")
        mock_cache.set = AsyncMock()

        # Pre-populate a product with reviews
        product = Product(name="Test Phone", brand="TestBrand", category="smartphones")
        db_session.add(product)
        await db_session.flush()

        reviewer = Reviewer(
            name="TestReviewer", platform=Platform.YOUTUBE,
            platform_id="youtube:test", credibility_score=0.5,
            is_active=True, is_verified=False
        )
        db_session.add(reviewer)
        await db_session.flush()

        review = Review(
            product_id=product.id, reviewer_id=reviewer.id,
            title="Test Review", content="This is a great phone.",
            platform_url="https://youtube.com/watch?v=test1234567",
            review_type=ReviewType.FULL_REVIEW,
            is_processed=True, processing_status=ProcessingStatus.COMPLETED
        )
        db_session.add(review)
        await db_session.commit()

        summary_json = json.dumps({
            "reviewer_summaries": [
                {
                    "reviewer_name": "TestReviewer",
                    "platform": "youtube",
                    "url": "https://youtube.com/watch?v=test1234567",
                    "summary": "Great phone overall."
                }
            ],
            "overall_summary": "The phone is highly recommended.",
            "common_pros": ["Good performance"],
            "common_cons": ["Battery could be better"]
        })
        mock_gemini_call.return_value = mock_gemini_response(summary_json)

        from app.functions.review_tools import get_reviews_summary
        result = await get_reviews_summary(db_session, {"product_name": "Test Phone"})

        assert result["status"] == "success"
        assert len(result["reviewer_summaries"]) == 1
        assert result["common_pros"]
        assert result["common_cons"]
        # Verify cache was set
        mock_cache.set.assert_called_once()
