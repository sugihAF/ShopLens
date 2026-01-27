"""Tests for gather functions - Phase 1 implementation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import execute_function, FUNCTION_DECLARATIONS


def test_gather_function_declarations_exist():
    """Test that new gather function declarations are present."""
    declared_names = [f["name"] for f in FUNCTION_DECLARATIONS]

    # Check all Phase 1 functions are declared
    assert "gather_product_reviews" in declared_names, "Missing gather_product_reviews declaration"
    assert "search_youtube_reviews" in declared_names, "Missing search_youtube_reviews declaration"
    assert "search_blog_reviews" in declared_names, "Missing search_blog_reviews declaration"


def test_gather_product_reviews_declaration_structure():
    """Test gather_product_reviews has correct parameter structure."""
    func = None
    for f in FUNCTION_DECLARATIONS:
        if f["name"] == "gather_product_reviews":
            func = f
            break

    assert func is not None
    assert "product_name" in func["parameters"]["properties"]
    assert func["parameters"]["properties"]["product_name"]["type"] == "string"
    assert "product_name" in func["parameters"]["required"]


def test_search_youtube_reviews_declaration_structure():
    """Test search_youtube_reviews has correct parameter structure."""
    func = None
    for f in FUNCTION_DECLARATIONS:
        if f["name"] == "search_youtube_reviews":
            func = f
            break

    assert func is not None
    assert "product_name" in func["parameters"]["properties"]
    assert "limit" in func["parameters"]["properties"]
    assert func["parameters"]["properties"]["product_name"]["type"] == "string"


def test_search_blog_reviews_declaration_structure():
    """Test search_blog_reviews has correct parameter structure."""
    func = None
    for f in FUNCTION_DECLARATIONS:
        if f["name"] == "search_blog_reviews":
            func = f
            break

    assert func is not None
    assert "product_name" in func["parameters"]["properties"]
    assert "limit" in func["parameters"]["properties"]


@pytest.mark.asyncio
async def test_gather_product_reviews_missing_product_name(db_session: AsyncSession):
    """Test gather_product_reviews returns error when product_name is missing."""
    result = await execute_function(
        db_session,
        "gather_product_reviews",
        {}  # Missing product_name
    )

    assert "error" in result
    assert "product_name" in result["error"].lower() or "required" in result["error"].lower()


@pytest.mark.asyncio
async def test_search_youtube_reviews_missing_product_name(db_session: AsyncSession):
    """Test search_youtube_reviews returns error when product_name is missing."""
    result = await execute_function(
        db_session,
        "search_youtube_reviews",
        {}  # Missing product_name
    )

    assert "error" in result


@pytest.mark.asyncio
async def test_search_blog_reviews_missing_product_name(db_session: AsyncSession):
    """Test search_blog_reviews returns error when product_name is missing."""
    result = await execute_function(
        db_session,
        "search_blog_reviews",
        {}  # Missing product_name
    )

    assert "error" in result


# Note: The following tests require GEMINI_API_KEY to be set
# They are marked to skip if the API key is not available

@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires GEMINI_API_KEY - run manually to verify")
async def test_search_youtube_reviews_with_product(db_session: AsyncSession):
    """Test search_youtube_reviews with valid product name.

    Expected output:
    {
        "status": "success",
        "urls": ["https://www.youtube.com/watch?v=...", ...],
        "product_name": "iPhone 15 Pro"
    }
    """
    result = await execute_function(
        db_session,
        "search_youtube_reviews",
        {"product_name": "iPhone 15 Pro", "limit": 3}
    )

    # Should not have error
    assert "error" not in result or result.get("status") == "success"
    assert "urls" in result
    assert isinstance(result["urls"], list)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires GEMINI_API_KEY - run manually to verify")
async def test_search_blog_reviews_with_product(db_session: AsyncSession):
    """Test search_blog_reviews with valid product name.

    Expected output:
    {
        "status": "success",
        "urls": ["https://www.theverge.com/...", ...],
        "product_name": "Sony WH-1000XM5"
    }
    """
    result = await execute_function(
        db_session,
        "search_blog_reviews",
        {"product_name": "Sony WH-1000XM5", "limit": 3}
    )

    # Should not have error
    assert "error" not in result or result.get("status") == "success"
    assert "urls" in result
    assert isinstance(result["urls"], list)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires GEMINI_API_KEY and FIRECRAWL_API_KEY - run manually to verify")
async def test_gather_product_reviews_full_flow(db_session: AsyncSession):
    """Test gather_product_reviews full flow.

    Expected output:
    {
        "status": "success",
        "product": {...},
        "reviews": [...],
        "sources": ["MKBHD", "The Verge", ...],
        "total_reviews": 5
    }
    """
    result = await execute_function(
        db_session,
        "gather_product_reviews",
        {"product_name": "iPhone 15 Pro"}
    )

    # Should have status
    assert "status" in result
    # If successful, should have product and reviews
    if result.get("status") == "success":
        assert "product" in result
        assert "reviews" in result
        assert "sources" in result
