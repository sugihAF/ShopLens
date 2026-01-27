"""Tests for marketplace functions."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.functions.registry import FUNCTION_DECLARATIONS, execute_function


class TestMarketplaceFunctionDeclarations:
    """Test that marketplace function declarations are properly defined."""

    def test_scrape_marketplace_listings_declaration_exists(self):
        """Test that scrape_marketplace_listings function is declared."""
        func_names = [f["name"] for f in FUNCTION_DECLARATIONS]
        assert "scrape_marketplace_listings" in func_names

    def test_find_marketplace_listings_declaration_exists(self):
        """Test that find_marketplace_listings function is declared."""
        func_names = [f["name"] for f in FUNCTION_DECLARATIONS]
        assert "find_marketplace_listings" in func_names

    def test_scrape_marketplace_listings_declaration_structure(self):
        """Test scrape_marketplace_listings declaration has correct structure."""
        func = next(f for f in FUNCTION_DECLARATIONS if f["name"] == "scrape_marketplace_listings")

        # Check required fields
        assert "description" in func
        assert "parameters" in func
        assert func["parameters"]["type"] == "object"

        # Check properties
        props = func["parameters"]["properties"]
        assert "product_name" in props
        assert props["product_name"]["type"] == "string"

        # Check required
        assert "product_name" in func["parameters"]["required"]

    def test_find_marketplace_listings_declaration_structure(self):
        """Test find_marketplace_listings declaration has correct structure."""
        func = next(f for f in FUNCTION_DECLARATIONS if f["name"] == "find_marketplace_listings")

        # Check required fields
        assert "description" in func
        assert "parameters" in func
        assert func["parameters"]["type"] == "object"

        # Check properties - should have both product_id and product_name options
        props = func["parameters"]["properties"]
        assert "product_id" in props or "product_name" in props

        # Description should mention auto-scraping
        assert "scrape" in func["description"].lower() or "amazon" in func["description"].lower()


class TestMarketplaceFunctionValidation:
    """Test marketplace function input validation."""

    @pytest.mark.asyncio
    async def test_scrape_marketplace_listings_missing_product_name(self, db_session):
        """Test that scrape_marketplace_listings returns error when product_name is missing."""
        result = await execute_function(db_session, "scrape_marketplace_listings", {})
        assert "error" in result
        assert "product_name" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_find_marketplace_listings_missing_both_params(self, db_session):
        """Test that find_marketplace_listings returns error when both params missing."""
        result = await execute_function(db_session, "find_marketplace_listings", {})
        assert "error" in result
        # Should require either product_id or product_name
        assert "product_id" in result["error"].lower() or "product_name" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_find_marketplace_listings_invalid_product_id(self, db_session):
        """Test that find_marketplace_listings handles invalid product_id."""
        result = await execute_function(db_session, "find_marketplace_listings", {"product_id": 999999})
        assert "error" in result or result.get("status") == "no_results"


class TestMarketplaceScraperService:
    """Test marketplace scraper service."""

    def test_marketplace_scraper_singleton(self):
        """Test that marketplace scraper is a singleton."""
        from app.services.marketplace_scraper import get_marketplace_scraper

        scraper1 = get_marketplace_scraper()
        scraper2 = get_marketplace_scraper()
        assert scraper1 is scraper2

    def test_marketplace_scraper_initialization(self):
        """Test marketplace scraper initializes correctly."""
        from app.services.marketplace_scraper import MarketplaceScraperService

        # This should not raise an exception even without API keys
        scraper = MarketplaceScraperService()
        assert scraper is not None


@pytest.mark.skipif(True, reason="Requires API keys for live testing")
class TestMarketplaceLiveIntegration:
    """Live integration tests for marketplace functions (requires API keys)."""

    @pytest.mark.asyncio
    async def test_scrape_amazon_listings(self, db_session):
        """Test scraping Amazon listings."""
        from app.services.marketplace_scraper import get_marketplace_scraper

        scraper = get_marketplace_scraper()
        result = await scraper.search_amazon("iPhone 15 Pro", limit=3)

        assert result is not None
        assert "listings" in result
        # May be empty if API key not set
        if result.get("status") == "success":
            assert len(result["listings"]) > 0

    @pytest.mark.asyncio
    async def test_scrape_ebay_listings(self, db_session):
        """Test scraping eBay listings."""
        from app.services.marketplace_scraper import get_marketplace_scraper

        scraper = get_marketplace_scraper()
        result = await scraper.search_ebay("Sony WH-1000XM5", limit=3)

        assert result is not None
        assert "listings" in result

    @pytest.mark.asyncio
    async def test_find_marketplace_listings_with_name(self, db_session):
        """Test find_marketplace_listings with product name."""
        result = await execute_function(
            db_session,
            "find_marketplace_listings",
            {"product_name": "MacBook Pro M3"}
        )

        assert result is not None
        # Should either return listings or no_results status
        assert "listings" in result or "status" in result

    @pytest.mark.asyncio
    async def test_full_marketplace_flow(self, db_session):
        """Test full flow: scrape then find listings."""
        # First scrape
        scrape_result = await execute_function(
            db_session,
            "scrape_marketplace_listings",
            {"product_name": "AirPods Pro 2"}
        )

        assert scrape_result is not None

        # Then find (should use cached data)
        find_result = await execute_function(
            db_session,
            "find_marketplace_listings",
            {"product_name": "AirPods Pro 2"}
        )

        assert find_result is not None
        assert "listings" in find_result or "status" in find_result
