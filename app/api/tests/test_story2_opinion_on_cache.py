"""Tests for Story 2: Opinion extraction on cached summaries."""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.reviewer import Reviewer
from app.models.review import Review


@pytest.fixture(scope="session")
def event_loop():
    """Override event_loop fixture for compatibility."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def product_with_reviews(db_session: AsyncSession):
    """Create a product with reviews but NO consensus data."""
    product = Product(
        name="Test Phone X",
        brand="TestBrand",
        category="smartphones",
    )
    db_session.add(product)
    await db_session.flush()

    reviewer = Reviewer(
        name="TestReviewer",
        platform="youtube",
        platform_id="UC_test_123",
        profile_url="https://youtube.com/@test",
    )
    db_session.add(reviewer)
    await db_session.flush()

    review = Review(
        product_id=product.id,
        reviewer_id=reviewer.id,
        title="Test Review",
        content="This phone has great battery life and an excellent camera. The display is vibrant.",
        platform_url="https://youtube.com/watch?v=test123",
    )
    db_session.add(review)
    await db_session.flush()
    await db_session.refresh(product)

    return product


@pytest.mark.asyncio
async def test_summary_returns_aspect_sentiments_key(db_session: AsyncSession, product_with_reviews):
    """get_reviews_summary result must include aspect_sentiments field."""
    from app.functions.review_tools import get_reviews_summary

    # Mock the LLM provider to return a valid summary + opinions
    mock_summary_response = '{"reviewer_summaries": [{"reviewer_name": "TestReviewer", "platform": "youtube", "url": "https://youtube.com/watch?v=test123", "summary": "Great phone overall."}], "overall_summary": "Test summary", "common_pros": ["battery"], "common_cons": ["price"]}'
    mock_opinions_response = '{"opinions": [{"reviewer_name": "TestReviewer", "aspect": "battery", "sentiment": 0.8, "confidence": 0.9, "quote": "great battery life", "summary": "Positive about battery"}]}'

    mock_provider = MagicMock()
    mock_provider.build_content = MagicMock(return_value="content")
    mock_provider.build_config = MagicMock(return_value="config")
    mock_provider.extract_text = MagicMock(side_effect=[mock_summary_response, mock_opinions_response])
    mock_provider.generate = AsyncMock(return_value="response")

    # Mock cache to return None (no cache hit) so we go through the full flow
    with patch("app.functions.review_tools.cache") as mock_cache, \
         patch("app.services.llm_service.get_llm_provider", return_value=mock_provider):
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_cache.hash_key = MagicMock(return_value="test_key")

        result = await get_reviews_summary(db_session, {"product_name": "Test Phone X"})

    assert result.get("status") == "success", f"Expected success, got: {result}"
    assert "aspect_sentiments" in result, (
        "get_reviews_summary must include aspect_sentiments in result"
    )


@pytest.mark.asyncio
async def test_cached_summary_triggers_extraction_when_no_consensus(
    db_session: AsyncSession, product_with_reviews
):
    """When summary is cached but consensus is empty, opinion extraction must run."""
    from app.functions.review_tools import get_reviews_summary
    from app.crud.consensus import consensus_crud

    # Verify no consensus exists initially
    consensus_list = await consensus_crud.get_by_product(db_session, product_id=product_with_reviews.id)
    assert len(consensus_list) == 0, "Precondition: no consensus should exist"

    # Create a cached summary (simulating a product ingested before opinion pipeline)
    cached_result = {
        "status": "success",
        "product": {"id": product_with_reviews.id, "name": "Test Phone X", "brand": "TestBrand", "category": "smartphones"},
        "reviewer_summaries": [{"reviewer_name": "TestReviewer", "platform": "youtube", "url": "https://youtube.com/watch?v=test123", "summary": "Great phone."}],
        "overall_summary": "Test overall summary",
        "common_pros": ["battery"],
        "common_cons": ["price"],
        "total_reviews": 1,
    }

    mock_opinions_response = '{"opinions": [{"reviewer_name": "TestReviewer", "aspect": "battery", "sentiment": 0.8, "confidence": 0.9, "quote": "great battery life", "summary": "Positive about battery"}]}'

    mock_provider = MagicMock()
    mock_provider.build_content = MagicMock(return_value="content")
    mock_provider.build_config = MagicMock(return_value="config")
    mock_provider.extract_text = MagicMock(return_value=mock_opinions_response)
    mock_provider.generate = AsyncMock(return_value="response")

    with patch("app.functions.review_tools.cache") as mock_cache, \
         patch("app.services.llm_service.get_llm_provider", return_value=mock_provider):
        mock_cache.get = AsyncMock(return_value=cached_result)
        mock_cache.set = AsyncMock()
        mock_cache.hash_key = MagicMock(return_value="test_key")

        result = await get_reviews_summary(db_session, {"product_name": "Test Phone X"})

    # After returning cached summary, consensus should now exist
    assert result.get("status") == "success"
    assert "aspect_sentiments" in result, (
        "Cached result must include aspect_sentiments after extraction"
    )

    consensus_list = await consensus_crud.get_by_product(db_session, product_id=product_with_reviews.id)
    assert len(consensus_list) > 0, (
        "Consensus should be populated even on cache hit when it was missing"
    )


@pytest.mark.asyncio
async def test_cached_summary_skips_extraction_when_consensus_exists(
    db_session: AsyncSession, product_with_reviews
):
    """When summary is cached AND consensus exists, no redundant extraction."""
    from app.functions.review_tools import get_reviews_summary
    from app.crud.consensus import consensus_crud

    # Pre-populate consensus
    await consensus_crud.upsert(
        db_session,
        product_id=product_with_reviews.id,
        aspect="battery",
        average_sentiment=0.8,
        agreement_score=0.9,
        review_count=1,
        details={"summary": "Good battery"},
    )
    await db_session.commit()

    cached_result = {
        "status": "success",
        "product": {"id": product_with_reviews.id, "name": "Test Phone X", "brand": "TestBrand", "category": "smartphones"},
        "reviewer_summaries": [{"reviewer_name": "TestReviewer", "platform": "youtube", "url": "https://youtube.com/watch?v=test123", "summary": "Great phone."}],
        "overall_summary": "Test overall summary",
        "common_pros": ["battery"],
        "common_cons": ["price"],
        "total_reviews": 1,
    }

    mock_provider = MagicMock()

    with patch("app.functions.review_tools.cache") as mock_cache, \
         patch("app.services.llm_service.get_llm_provider", return_value=mock_provider) as mock_get_provider:
        mock_cache.get = AsyncMock(return_value=cached_result)
        mock_cache.set = AsyncMock()
        mock_cache.hash_key = MagicMock(return_value="test_key")

        result = await get_reviews_summary(db_session, {"product_name": "Test Phone X"})

    # LLM should NOT have been called for opinion extraction since consensus exists
    mock_provider.generate.assert_not_called()
    assert result.get("status") == "success"
    assert "aspect_sentiments" in result


@pytest.mark.asyncio
async def test_aspect_sentiments_structure(db_session: AsyncSession, product_with_reviews):
    """aspect_sentiments must have correct structure."""
    from app.functions.review_tools import get_reviews_summary

    mock_summary_response = '{"reviewer_summaries": [{"reviewer_name": "TestReviewer", "platform": "youtube", "url": "https://youtube.com/watch?v=test123", "summary": "Great phone."}], "overall_summary": "Summary", "common_pros": ["battery"], "common_cons": ["price"]}'
    mock_opinions_response = '{"opinions": [{"reviewer_name": "TestReviewer", "aspect": "battery", "sentiment": 0.8, "confidence": 0.9, "quote": "great battery", "summary": "Positive"}, {"reviewer_name": "TestReviewer", "aspect": "camera", "sentiment": 0.6, "confidence": 0.85, "quote": "good camera", "summary": "Decent camera"}]}'

    mock_provider = MagicMock()
    mock_provider.build_content = MagicMock(return_value="content")
    mock_provider.build_config = MagicMock(return_value="config")
    mock_provider.extract_text = MagicMock(side_effect=[mock_summary_response, mock_opinions_response])
    mock_provider.generate = AsyncMock(return_value="response")

    with patch("app.functions.review_tools.cache") as mock_cache, \
         patch("app.services.llm_service.get_llm_provider", return_value=mock_provider):
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_cache.hash_key = MagicMock(return_value="test_key")

        result = await get_reviews_summary(db_session, {"product_name": "Test Phone X"})

    sentiments = result.get("aspect_sentiments", [])
    assert len(sentiments) >= 1, "Should have at least 1 aspect sentiment"

    for s in sentiments:
        assert "aspect" in s, "Each sentiment must have 'aspect'"
        assert "average_sentiment" in s, "Each sentiment must have 'average_sentiment'"
        assert "positive_pct" in s, "Each sentiment must have 'positive_pct'"
        assert "negative_pct" in s, "Each sentiment must have 'negative_pct'"
        assert "review_count" in s, "Each sentiment must have 'review_count'"
        assert "agreement_score" in s, "Each sentiment must have 'agreement_score'"
        assert -1.0 <= s["average_sentiment"] <= 1.0
        assert 0 <= s["positive_pct"] <= 100
        assert 0 <= s["negative_pct"] <= 100


@pytest.mark.asyncio
async def test_opinions_are_persisted(db_session: AsyncSession, product_with_reviews):
    """Opinion records must be saved to the database after extraction."""
    from app.functions.review_tools import get_reviews_summary
    from app.models.opinion import Opinion
    from sqlalchemy import select

    mock_summary_response = '{"reviewer_summaries": [{"reviewer_name": "TestReviewer", "platform": "youtube", "url": "https://youtube.com/watch?v=test123", "summary": "Great phone."}], "overall_summary": "Summary", "common_pros": ["battery"], "common_cons": ["price"]}'
    mock_opinions_response = '{"opinions": [{"reviewer_name": "TestReviewer", "aspect": "battery", "sentiment": 0.8, "confidence": 0.9, "quote": "great battery", "summary": "Positive about battery"}]}'

    mock_provider = MagicMock()
    mock_provider.build_content = MagicMock(return_value="content")
    mock_provider.build_config = MagicMock(return_value="config")
    mock_provider.extract_text = MagicMock(side_effect=[mock_summary_response, mock_opinions_response])
    mock_provider.generate = AsyncMock(return_value="response")

    with patch("app.functions.review_tools.cache") as mock_cache, \
         patch("app.services.llm_service.get_llm_provider", return_value=mock_provider):
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_cache.hash_key = MagicMock(return_value="test_key")

        await get_reviews_summary(db_session, {"product_name": "Test Phone X"})

    # Check opinions were persisted
    result = await db_session.execute(select(Opinion))
    opinions = list(result.scalars().all())
    assert len(opinions) > 0, "Opinion records must be saved to the database"
    assert opinions[0].aspect == "battery"
    assert opinions[0].sentiment == pytest.approx(0.8, abs=0.01)
