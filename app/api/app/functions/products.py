"""Product-related functions for Gemini function calling."""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import register_function
from app.crud.product import product_crud


@register_function("search_products")
async def search_products(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for products by name, category, or keywords.

    Args:
        db: Database session
        args: {query: str, category?: str, limit?: int}

    Returns:
        List of matching products
    """
    query = args.get("query", "")
    category = args.get("category")
    limit = min(args.get("limit", 5), 20)

    products = await product_crud.search(
        db,
        query=query,
        category=category,
        limit=limit
    )

    if not products:
        return {
            "products": [],
            "total": 0,
            "message": f"No products found for '{query}'" + (f" in category '{category}'" if category else ""),
            "suggestion": f"To get reviews for '{query}', use the gather_product_reviews function with product_name='{query}'. This will search YouTube and tech blogs for reviews and ingest them into the database."
        }

    return {
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "category": p.category,
                "model_number": p.model_number,
                "review_count": p.review_count,
                "average_rating": float(p.average_rating) if p.average_rating else None,
                "description": p.description[:200] + "..." if p.description and len(p.description) > 200 else p.description
            }
            for p in products
        ],
        "total": len(products),
        "query": query,
        "category": category
    }


@register_function("get_product_details")
async def get_product_details(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get detailed information about a specific product.

    Args:
        db: Database session
        args: {product_id: int}

    Returns:
        Detailed product information
    """
    product_id = args.get("product_id")
    if not product_id:
        return {"error": "product_id is required"}

    product = await product_crud.get(db, id=product_id)

    if not product:
        return {"error": f"Product with ID {product_id} not found"}

    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "model_number": product.model_number,
        "description": product.description,
        "specifications": product.specifications or {},
        "release_date": product.release_date.isoformat() if product.release_date else None,
        "review_count": product.review_count,
        "average_rating": float(product.average_rating) if product.average_rating else None,
        "image_url": product.image_url,
        "official_url": product.official_url
    }
