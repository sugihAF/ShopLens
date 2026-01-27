"""Marketplace functions for Gemini function calling."""

from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import register_function
from app.crud.product import product_crud
from app.models.marketplace import MarketplaceListing
from app.core.logging import get_logger

logger = get_logger(__name__)

# Cache TTL for marketplace listings (24 hours)
MARKETPLACE_CACHE_TTL_HOURS = 24


def _is_listing_fresh(last_checked: Optional[datetime], ttl_hours: int = MARKETPLACE_CACHE_TTL_HOURS) -> bool:
    """Check if marketplace listing data is still fresh based on TTL."""
    if not last_checked:
        return False
    now = datetime.now(timezone.utc)
    # Handle timezone-naive datetime
    if last_checked.tzinfo is None:
        last_checked = last_checked.replace(tzinfo=timezone.utc)
    age = now - last_checked
    return age < timedelta(hours=ttl_hours)


@register_function("scrape_marketplace_listings")
async def scrape_marketplace_listings(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape current prices and availability from Amazon and eBay for a product.

    Use this when user asks where to buy a product. This will search marketplaces
    and store the listings in the database.

    Args:
        db: Database session
        args: {
            product_name: str - Product to search for,
            product_id?: int - Optional product ID to associate listings,
            marketplaces?: list[str] - Marketplaces to search (default: ["amazon", "ebay"]),
            country?: str - Country code (default: "US")
        }

    Returns:
        Dictionary with scraped listings from each marketplace
    """
    from app.services.marketplace_scraper import get_marketplace_scraper

    product_name = args.get("product_name")
    product_id = args.get("product_id")
    marketplaces = args.get("marketplaces", ["amazon", "ebay"])
    country = args.get("country", "US")

    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Scraping marketplace listings for: {product_name}")

    # Get or search for product ID if not provided
    if not product_id and product_name:
        products = await product_crud.search(db, query=product_name, limit=1)
        if products:
            product_id = products[0].id
            logger.info(f"Found product ID {product_id} for '{product_name}'")

    # Get marketplace scraper service
    scraper = get_marketplace_scraper()

    # Scrape and store listings
    result = await scraper.scrape_and_store_listings(
        db=db,
        product_name=product_name,
        product_id=product_id,
        marketplaces=marketplaces,
        country=country
    )

    return result


@register_function("find_marketplace_listings")
async def find_marketplace_listings(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find where to buy a product with current prices from various marketplaces.

    This function first checks the database for existing listings. If no listings
    exist or they are stale (>24 hours old), it will automatically scrape fresh
    listings from Amazon and eBay.

    Args:
        db: Database session
        args: {
            product_id?: int - Product ID to find listings for,
            product_name?: str - Product name (used if product_id not provided),
            country?: str - Country code (default: "US"),
            force_refresh?: bool - Force scraping even if cache is fresh
        }

    Returns:
        List of marketplace listings with prices, sorted by price
    """
    product_id = args.get("product_id")
    product_name = args.get("product_name")
    country = args.get("country", "US")
    force_refresh = args.get("force_refresh", False)

    # Need either product_id or product_name
    if not product_id and not product_name:
        return {"error": "Either product_id or product_name is required"}

    # Get product
    product = None
    if product_id:
        product = await product_crud.get(db, id=product_id)
        if not product:
            return {"error": f"Product with ID {product_id} not found"}
        product_name = product.name
    else:
        # Search for product by name
        products = await product_crud.search(db, query=product_name, limit=1)
        if products:
            product = products[0]
            product_id = product.id
        else:
            # Product not in database - we can still search marketplaces
            logger.info(f"Product '{product_name}' not in database, searching marketplaces directly")

    # Query existing marketplace listings - use correct column names
    listings = []
    has_fresh_data = False

    if product_id:
        result = await db.execute(
            select(MarketplaceListing)
            .where(MarketplaceListing.product_id == product_id)
            .where(MarketplaceListing.country_code == country)
            .order_by(MarketplaceListing.price_current)
        )
        listings = list(result.scalars().all())

        # Check if we have fresh data
        if listings and not force_refresh:
            # Check if most recent listing is fresh
            most_recent = max(
                listings,
                key=lambda l: l.last_checked if l.last_checked else datetime.min.replace(tzinfo=timezone.utc)
            )
            has_fresh_data = _is_listing_fresh(most_recent.last_checked)

    # If no listings or stale data, scrape fresh listings
    if not listings or not has_fresh_data or force_refresh:
        logger.info(f"Scraping fresh marketplace listings for '{product_name}' (force_refresh={force_refresh}, has_listings={len(listings)}, fresh={has_fresh_data})")

        # Scrape new listings
        scrape_result = await scrape_marketplace_listings(db, {
            "product_name": product_name,
            "product_id": product_id,
            "marketplaces": ["amazon", "ebay"],
            "country": country
        })

        if scrape_result.get("status") == "success":
            # Check if we have listings (either stored or found without product_id)
            listings_found = scrape_result.get("listings_found", 0)
            listings_stored = scrape_result.get("listings_stored", 0)
            scraped_listings = scrape_result.get("listings", [])

            if listings_stored > 0 and product_id:
                # Re-query to get the new listings from DB
                result = await db.execute(
                    select(MarketplaceListing)
                    .where(MarketplaceListing.product_id == product_id)
                    .where(MarketplaceListing.country_code == country)
                    .where(MarketplaceListing.is_available == True)
                    .order_by(MarketplaceListing.price_current)
                )
                listings = list(result.scalars().all())
            elif listings_found > 0 and scraped_listings:
                # Return the scraped results directly if no product_id (couldn't store to DB)
                return {
                    "status": "success",
                    "product_name": product_name,
                    "country": country,
                    "currency": "USD",
                    "listings": scraped_listings,
                    "total_listings": len(scraped_listings),
                    "freshly_scraped": True,
                    "message": f"Found {len(scraped_listings)} listings for '{product_name}'"
                }
        elif not listings:
            # No existing listings and scraping failed/found nothing
            return {
                "status": "no_results",
                "product_id": product_id,
                "product_name": product_name,
                "country": country,
                "listings": [],
                "total_listings": 0,
                "message": f"No marketplace listings found for '{product_name}'. Try a different search term.",
                "scrape_result": scrape_result
            }

    # Filter out unavailable items
    available_listings = [l for l in listings if l.is_available is True or l.is_available is None]

    if not available_listings:
        return {
            "status": "out_of_stock",
            "product_id": product_id,
            "product_name": product.name if product else product_name,
            "country": country,
            "listings": [],
            "total_listings": 0,
            "message": f"All listings for '{product.name if product else product_name}' are currently out of stock"
        }

    # Calculate price range
    prices = [float(l.price_current) for l in available_listings if l.price_current]
    lowest_price = min(prices) if prices else None
    highest_price = max(prices) if prices else None

    # Format response
    formatted_listings = []
    best_sellers = []
    best_reviewed = []
    cheapest = []

    for l in available_listings:
        listing_data = {
            "marketplace": l.marketplace_name,
            "title": l.listing_metadata.get('title') if l.listing_metadata else None,
            "seller": l.seller_name,
            "seller_rating": float(l.seller_rating) if l.seller_rating else None,
            "review_count": l.listing_metadata.get('review_count') if l.listing_metadata else None,
            "price_current": float(l.price_current) if l.price_current else None,
            "price_original": float(l.price_original) if l.price_original else None,
            "discount_percent": _calculate_discount(
                float(l.price_original) if l.price_original else None,
                float(l.price_current) if l.price_current else None
            ),
            "url": l.listing_url,
            "in_stock": l.is_available is True,
            "is_best_seller": l.listing_metadata.get('is_best_seller', False) if l.listing_metadata else False,
            "shipping_info": l.shipping_info,
            "last_updated": l.last_checked.isoformat() if l.last_checked else None
        }
        formatted_listings.append(listing_data)

        # Categorize listings
        if listing_data.get("is_best_seller"):
            best_sellers.append(listing_data)
        if listing_data.get("seller_rating") and listing_data["seller_rating"] >= 4.5:
            best_reviewed.append(listing_data)

    # Sort by price for cheapest
    sorted_by_price = sorted(formatted_listings, key=lambda x: x.get("price_current") or float('inf'))
    cheapest = sorted_by_price[:3]

    return {
        "status": "success",
        "product_id": product_id,
        "product_name": product.name if product else product_name,
        "country": country,
        "currency": available_listings[0].currency if available_listings else "USD",
        "price_range": {
            "lowest": lowest_price,
            "highest": highest_price
        },
        "recommendations": {
            "cheapest": cheapest,
            "best_sellers": best_sellers[:3],
            "best_reviewed": sorted(best_reviewed, key=lambda x: x.get("seller_rating") or 0, reverse=True)[:3]
        },
        "listings": formatted_listings,
        "total_listings": len(formatted_listings),
        "freshly_scraped": not has_fresh_data or force_refresh
    }


def _calculate_discount(original: Optional[float], current: Optional[float]) -> int:
    """Calculate discount percentage."""
    if not original or not current or original <= current:
        return 0
    return int(((original - current) / original) * 100)
