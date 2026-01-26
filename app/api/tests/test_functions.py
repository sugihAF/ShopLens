"""Tests for function registry and implementations."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import execute_function, FUNCTION_DECLARATIONS


def test_function_declarations_structure():
    """Test that function declarations have correct structure."""
    assert len(FUNCTION_DECLARATIONS) > 0

    for func in FUNCTION_DECLARATIONS:
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
        assert func["parameters"]["type"] == "object"
        assert "properties" in func["parameters"]
        assert "required" in func["parameters"]


def test_all_required_functions_exist():
    """Test that all required functions are declared."""
    required_functions = [
        "search_products",
        "get_product_details",
        "get_product_reviews",
        "get_review_consensus",
        "compare_products",
        "find_marketplace_listings",
        "get_reviewer_info",
        "semantic_search",
    ]

    declared_names = [f["name"] for f in FUNCTION_DECLARATIONS]

    for func_name in required_functions:
        assert func_name in declared_names, f"Missing function: {func_name}"


@pytest.mark.asyncio
async def test_execute_unknown_function(db_session: AsyncSession):
    """Test executing unknown function returns error."""
    result = await execute_function(db_session, "unknown_function", {})

    assert "error" in result
    assert "unknown function" in result["error"].lower()


@pytest.mark.asyncio
async def test_search_products_empty_query(db_session: AsyncSession):
    """Test search products with empty database."""
    result = await execute_function(
        db_session,
        "search_products",
        {"query": "iPhone"}
    )

    assert "products" in result
    assert "total" in result
    assert isinstance(result["products"], list)


@pytest.mark.asyncio
async def test_get_product_details_not_found(db_session: AsyncSession):
    """Test get product details for non-existent product."""
    result = await execute_function(
        db_session,
        "get_product_details",
        {"product_id": 99999}
    )

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_compare_products_validation(db_session: AsyncSession):
    """Test compare products validation."""
    # Less than 2 products
    result = await execute_function(
        db_session,
        "compare_products",
        {"product_ids": [1]}
    )
    assert "error" in result
    assert "at least 2" in result["error"].lower()

    # More than 5 products
    result = await execute_function(
        db_session,
        "compare_products",
        {"product_ids": [1, 2, 3, 4, 5, 6]}
    )
    assert "error" in result
    assert "maximum 5" in result["error"].lower()
