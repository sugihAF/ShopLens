"""Marketplace scraper service for fetching product listings from Amazon and eBay."""

import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging import get_logger
from app.models.marketplace import MarketplaceListing
from app.models.product import Product
from app.crud.product import product_crud

logger = get_logger(__name__)

# Cache TTL for marketplace listings (24 hours)
MARKETPLACE_CACHE_TTL_HOURS = 24

# Extraction prompt for parsing marketplace data
EXTRACTION_PROMPT = """You are an expert at extracting structured product listing data from marketplace pages.

Analyze the following marketplace search results and extract the top product listings.

IMPORTANT: Only extract information that is explicitly shown in the content. Do not make up data.

Return a JSON object with this structure:
{
    "listings": [
        {
            "title": "Full product title",
            "price": 999.99,
            "currency": "USD",
            "original_price": 1099.99,
            "url": "Full product URL",
            "seller_name": "Seller or store name",
            "seller_rating": 4.5,
            "review_count": 1234,
            "availability": "in_stock",
            "is_best_seller": false,
            "shipping_info": "Free shipping" or null,
            "image_url": "Product image URL" or null
        }
    ]
}

For availability, use one of: "in_stock", "out_of_stock", "pre_order", "unknown"

If you cannot determine certain fields, use null.

Marketplace content:
---
{content}
---

Return ONLY the JSON object, no additional text."""


class MarketplaceScraperService:
    """
    Service for scraping product listings from marketplaces like Amazon and eBay.

    Uses Gemini with Google Search grounding to find real product listings.
    """

    def __init__(self):
        """Initialize Gemini client."""
        self.genai_client = None
        self._init_clients()

    def _init_clients(self):
        """Initialize API clients."""
        # Initialize Gemini client
        if settings.GEMINI_API_KEY:
            try:
                self.genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Marketplace scraper Gemini client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
        else:
            logger.warning("GEMINI_API_KEY not set - marketplace scraping will not work")

    async def search_amazon(self, product_name: str, limit: int = 5) -> Dict[str, Any]:
        """
        Search Amazon for product listings using Gemini with Google Search grounding.

        Args:
            product_name: Product to search for
            limit: Maximum number of listings to return

        Returns:
            Dictionary with listings data
        """
        if not self.genai_client:
            return {"error": "Gemini client not initialized", "listings": []}

        logger.info(f"Searching Amazon for: {product_name}")

        search_prompt = f"""Search Amazon for "{product_name}" and find the top {limit} product listings.

For each listing, I need:
1. Product title
2. Current price (in USD)
3. Original price if discounted
4. Direct product URL on Amazon
5. Seller/store name
6. Seller rating (out of 5)
7. Number of customer reviews
8. Stock availability
9. Whether it's a Best Seller
10. Shipping information

Return your response as a JSON object:
{{
    "listings": [
        {{
            "title": "Product title",
            "price": 99.99,
            "currency": "USD",
            "original_price": 129.99,
            "url": "https://www.amazon.com/dp/...",
            "seller_name": "Amazon.com" or seller name,
            "seller_rating": 4.5,
            "review_count": 12345,
            "availability": "in_stock",
            "is_best_seller": true,
            "shipping_info": "Free Prime shipping"
        }}
    ],
    "marketplace": "amazon"
}}

Only include real product listings. Do not make up data."""

        try:
            response = await self.genai_client.aio.models.generate_content(
                model=settings.LLM_MODEL,
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2
                )
            )

            response_text = response.text

            # Parse JSON response
            try:
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    data = json.loads(json_match.group())
                    listings = data.get("listings", [])
                    logger.info(f"Found {len(listings)} Amazon listings for {product_name}")
                    return {
                        "status": "success",
                        "marketplace": "amazon",
                        "listings": listings[:limit],
                        "product_name": product_name
                    }
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Amazon search JSON: {e}")

            return {
                "status": "no_results",
                "marketplace": "amazon",
                "listings": [],
                "product_name": product_name
            }

        except Exception as e:
            logger.error(f"Error searching Amazon: {e}", exc_info=True)
            return {
                "error": str(e),
                "marketplace": "amazon",
                "listings": [],
                "product_name": product_name
            }

    async def search_ebay(self, product_name: str, limit: int = 5) -> Dict[str, Any]:
        """
        Search eBay for product listings using Gemini with Google Search grounding.

        Args:
            product_name: Product to search for
            limit: Maximum number of listings to return

        Returns:
            Dictionary with listings data
        """
        if not self.genai_client:
            return {"error": "Gemini client not initialized", "listings": []}

        logger.info(f"Searching eBay for: {product_name}")

        search_prompt = f"""Search eBay for "{product_name}" and find the top {limit} product listings.

For each listing, I need:
1. Product title
2. Current price (in USD)
3. Original price if applicable
4. Direct product URL on eBay
5. Seller name
6. Seller rating percentage
7. Number of items sold or reviews
8. Stock availability
9. Shipping information

Return your response as a JSON object:
{{
    "listings": [
        {{
            "title": "Product title",
            "price": 99.99,
            "currency": "USD",
            "original_price": null,
            "url": "https://www.ebay.com/itm/...",
            "seller_name": "seller_username",
            "seller_rating": 99.5,
            "review_count": 5000,
            "availability": "in_stock",
            "is_best_seller": false,
            "shipping_info": "Free shipping"
        }}
    ],
    "marketplace": "ebay"
}}

Only include real product listings. Do not make up data."""

        try:
            response = await self.genai_client.aio.models.generate_content(
                model=settings.LLM_MODEL,
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2
                )
            )

            response_text = response.text

            # Parse JSON response
            try:
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    data = json.loads(json_match.group())
                    listings = data.get("listings", [])
                    logger.info(f"Found {len(listings)} eBay listings for {product_name}")
                    return {
                        "status": "success",
                        "marketplace": "ebay",
                        "listings": listings[:limit],
                        "product_name": product_name
                    }
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse eBay search JSON: {e}")

            return {
                "status": "no_results",
                "marketplace": "ebay",
                "listings": [],
                "product_name": product_name
            }

        except Exception as e:
            logger.error(f"Error searching eBay: {e}", exc_info=True)
            return {
                "error": str(e),
                "marketplace": "ebay",
                "listings": [],
                "product_name": product_name
            }

    async def scrape_and_store_listings(
        self,
        db: AsyncSession,
        product_name: str,
        product_id: Optional[int] = None,
        marketplaces: List[str] = None,
        country: str = "US"
    ) -> Dict[str, Any]:
        """
        Scrape marketplace listings and store them in the database.

        Args:
            db: Database session
            product_name: Product to search for
            product_id: Optional product ID to associate listings with
            marketplaces: List of marketplaces to search (default: amazon, ebay)
            country: Country code for listings

        Returns:
            Dictionary with stored listings summary
        """
        if marketplaces is None:
            marketplaces = ["amazon", "ebay"]

        logger.info(f"Scraping listings for '{product_name}' from {marketplaces}")

        all_listings = []
        results_by_marketplace = {}

        # Search each marketplace
        import asyncio
        search_tasks = []

        if "amazon" in marketplaces:
            search_tasks.append(("amazon", self.search_amazon(product_name, limit=5)))
        if "ebay" in marketplaces:
            search_tasks.append(("ebay", self.search_ebay(product_name, limit=5)))

        # Execute searches in parallel
        for marketplace, task in search_tasks:
            try:
                result = await task
                results_by_marketplace[marketplace] = result
                if result.get("listings"):
                    all_listings.extend([
                        {**listing, "marketplace": marketplace}
                        for listing in result["listings"]
                    ])
            except Exception as e:
                logger.error(f"Error searching {marketplace}: {e}")
                results_by_marketplace[marketplace] = {"error": str(e), "listings": []}

        if not all_listings:
            return {
                "status": "no_results",
                "message": f"No listings found for '{product_name}'",
                "product_name": product_name,
                "marketplaces_searched": marketplaces,
                "listings_stored": 0
            }

        # If no product_id, return listings without storing to DB (product_id is required by DB schema)
        if product_id is None:
            logger.warning(f"No product_id for '{product_name}', returning listings without storing to DB")
            return {
                "status": "success",
                "product_name": product_name,
                "product_id": None,
                "marketplaces_searched": marketplaces,
                "listings_found": len(all_listings),
                "listings_stored": 0,
                "listings": [{
                    "marketplace": l.get("marketplace"),
                    "title": l.get("title"),
                    "price": l.get("price"),
                    "url": l.get("url"),
                    "seller_name": l.get("seller_name"),
                    "is_available": l.get("availability", "unknown").lower() == "in_stock"
                } for l in all_listings],
                "results_by_marketplace": {
                    k: {"count": len(v.get("listings", [])), "status": v.get("status", "unknown")}
                    for k, v in results_by_marketplace.items()
                }
            }

        # Store listings in database
        stored_count = 0
        stored_listings = []

        for listing_data in all_listings:
            try:
                # Map availability string to boolean
                availability_str = listing_data.get("availability", "unknown").lower()
                is_available = availability_str == "in_stock"

                # Convert seller_rating to Decimal if it's a percentage (for eBay)
                seller_rating = listing_data.get("seller_rating")
                if seller_rating and seller_rating > 5:
                    # eBay uses percentage ratings, convert to 5-star scale
                    seller_rating = seller_rating / 20.0  # 100% -> 5.0

                # Create listing record with correct column names matching the DB schema
                listing = MarketplaceListing(
                    product_id=product_id,
                    marketplace_name=listing_data.get("marketplace", "unknown"),
                    country_code=country,
                    listing_url=listing_data.get("url", ""),
                    price_current=Decimal(str(listing_data.get("price", 0))) if listing_data.get("price") else None,
                    price_original=Decimal(str(listing_data.get("original_price", 0))) if listing_data.get("original_price") else None,
                    currency=listing_data.get("currency", "USD"),
                    is_available=is_available,
                    seller_name=listing_data.get("seller_name"),
                    seller_rating=Decimal(str(seller_rating)) if seller_rating else None,
                    shipping_info=listing_data.get("shipping_info"),
                    listing_metadata={
                        "title": listing_data.get("title"),
                        "review_count": listing_data.get("review_count"),
                        "is_best_seller": listing_data.get("is_best_seller", False),
                        "image_url": listing_data.get("image_url"),
                        "scraped_at": datetime.now(timezone.utc).isoformat()
                    },
                    last_checked=datetime.now(timezone.utc)
                )

                db.add(listing)
                stored_count += 1
                stored_listings.append({
                    "marketplace": listing_data.get("marketplace"),
                    "title": listing_data.get("title"),
                    "price": listing_data.get("price"),
                    "url": listing_data.get("url")
                })

            except Exception as e:
                logger.error(f"Error storing listing: {e}")
                continue

        # Commit changes
        await db.commit()

        logger.info(f"Stored {stored_count} listings for '{product_name}'")

        return {
            "status": "success",
            "product_name": product_name,
            "product_id": product_id,
            "marketplaces_searched": marketplaces,
            "listings_found": len(all_listings),
            "listings_stored": stored_count,
            "listings": stored_listings,
            "results_by_marketplace": {
                k: {"count": len(v.get("listings", [])), "status": v.get("status", "unknown")}
                for k, v in results_by_marketplace.items()
            }
        }


# Global service instance
_marketplace_scraper: Optional[MarketplaceScraperService] = None


def get_marketplace_scraper() -> MarketplaceScraperService:
    """Get or create the marketplace scraper singleton."""
    global _marketplace_scraper
    if _marketplace_scraper is None:
        _marketplace_scraper = MarketplaceScraperService()
    return _marketplace_scraper
