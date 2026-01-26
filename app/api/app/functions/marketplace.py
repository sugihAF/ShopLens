"""Marketplace functions for Gemini function calling."""

from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import register_function
from app.crud.product import product_crud
from app.models.marketplace import MarketplaceListing, AvailabilityStatus


@register_function("find_marketplace_listings")
async def find_marketplace_listings(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find where to buy a product with current prices from various marketplaces.

    Args:
        db: Database session
        args: {product_id: int, country?: str}

    Returns:
        List of marketplace listings with prices
    """
    product_id = args.get("product_id")
    country = args.get("country", "ID")  # Default to Indonesia

    if not product_id:
        return {"error": "product_id is required"}

    # First check if product exists
    product = await product_crud.get(db, id=product_id)
    if not product:
        return {"error": f"Product with ID {product_id} not found"}

    # Query marketplace listings
    result = await db.execute(
        select(MarketplaceListing)
        .where(MarketplaceListing.product_id == product_id)
        .where(MarketplaceListing.country == country)
        .where(MarketplaceListing.availability != AvailabilityStatus.OUT_OF_STOCK)
        .order_by(MarketplaceListing.price)
    )
    listings = list(result.scalars().all())

    if not listings:
        return {
            "product_id": product_id,
            "product_name": product.name,
            "country": country,
            "listings": [],
            "message": f"No marketplace listings found for {product.name} in {country}"
        }

    # Find best price
    prices = [l.price for l in listings if l.price]
    lowest_price = min(prices) if prices else None
    highest_price = max(prices) if prices else None

    return {
        "product_id": product_id,
        "product_name": product.name,
        "country": country,
        "currency": listings[0].currency if listings else "IDR",
        "price_range": {
            "lowest": float(lowest_price) if lowest_price else None,
            "highest": float(highest_price) if highest_price else None
        },
        "listings": [
            {
                "marketplace": l.marketplace.value,
                "seller": l.listing_metadata.get('seller_name') if l.listing_metadata else None,
                "seller_rating": float(l.listing_metadata.get('seller_rating')) if l.listing_metadata and l.listing_metadata.get('seller_rating') else None,
                "price_current": float(l.price) if l.price else None,
                "price_original": float(l.original_price) if l.original_price else None,
                "discount_percent": _calculate_discount(l.original_price, l.price),
                "url": l.url,
                "in_stock": l.availability != AvailabilityStatus.OUT_OF_STOCK,
                "shipping_info": l.listing_metadata.get('shipping_estimate') if l.listing_metadata else None,
                "last_updated": l.last_checked_at.isoformat() if l.last_checked_at else None
            }
            for l in listings
        ],
        "total_listings": len(listings)
    }


def _calculate_discount(original: float, current: float) -> int:
    """Calculate discount percentage."""
    if not original or not current or original <= current:
        return 0
    return int(((original - current) / original) * 100)
