"""Review-related functions for Gemini function calling."""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import register_function
from app.crud.review import review_crud
from app.crud.product import product_crud


@register_function("get_product_reviews")
async def get_product_reviews(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get reviews for a product from trusted tech reviewers.

    Args:
        db: Database session
        args: {product_id: int, limit?: int}

    Returns:
        List of reviews for the product
    """
    product_id = args.get("product_id")
    if not product_id:
        return {"error": "product_id is required"}

    limit = min(args.get("limit", 5), 20)

    # First check if product exists
    product = await product_crud.get(db, id=product_id)
    if not product:
        return {"error": f"Product with ID {product_id} not found"}

    reviews = await review_crud.get_by_product(db, product_id=product_id, limit=limit)

    if not reviews:
        return {
            "product_id": product_id,
            "product_name": product.name,
            "reviews": [],
            "total": 0,
            "message": f"No reviews found for {product.name}"
        }

    return {
        "product_id": product_id,
        "product_name": product.name,
        "reviews": [
            {
                "id": r.id,
                "reviewer_name": r.reviewer.name if r.reviewer else "Unknown",
                "reviewer_platform": r.reviewer.platform if r.reviewer else None,
                "reviewer_channel": r.reviewer.channel_name if r.reviewer else None,
                "title": r.title,
                "summary": r.content[:500] + "..." if r.content and len(r.content) > 500 else r.content,
                "overall_rating": float(r.overall_rating) if r.overall_rating else None,
                "platform_url": r.platform_url,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "pros": r.review_metadata.get("pros", []) if r.review_metadata else [],
                "cons": r.review_metadata.get("cons", []) if r.review_metadata else []
            }
            for r in reviews
        ],
        "total": len(reviews)
    }


@register_function("get_review_consensus")
async def get_review_consensus(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get aggregated consensus from all reviewers about a product.

    Args:
        db: Database session
        args: {product_id: int}

    Returns:
        Consensus data showing what reviewers agree/disagree on
    """
    from app.crud.consensus import consensus_crud

    product_id = args.get("product_id")
    if not product_id:
        return {"error": "product_id is required"}

    # First check if product exists
    product = await product_crud.get(db, id=product_id)
    if not product:
        return {"error": f"Product with ID {product_id} not found"}

    consensus_list = await consensus_crud.get_by_product(db, product_id=product_id)

    if not consensus_list:
        return {
            "product_id": product_id,
            "product_name": product.name,
            "aspects": [],
            "message": f"No consensus data available for {product.name}. This product may not have enough reviews yet."
        }

    # Format sentiment as human-readable
    def format_sentiment(score: float) -> str:
        if score >= 0.6:
            return "very positive"
        elif score >= 0.2:
            return "positive"
        elif score >= -0.2:
            return "mixed/neutral"
        elif score >= -0.6:
            return "negative"
        else:
            return "very negative"

    def format_agreement(score: float) -> str:
        if score >= 0.8:
            return "strong agreement"
        elif score >= 0.6:
            return "general agreement"
        elif score >= 0.4:
            return "mixed opinions"
        else:
            return "reviewers disagree"

    return {
        "product_id": product_id,
        "product_name": product.name,
        "overall_review_count": product.review_count,
        "average_rating": float(product.average_rating) if product.average_rating else None,
        "aspects": [
            {
                "aspect": c.aspect,
                "sentiment_score": float(c.average_sentiment),
                "sentiment": format_sentiment(c.average_sentiment),
                "agreement_score": float(c.agreement_score),
                "agreement": format_agreement(c.agreement_score),
                "review_count": c.review_count,
                "summary": c.details.get("summary") if c.details else None,
                "key_points": c.details.get("key_points", []) if c.details else []
            }
            for c in consensus_list
        ]
    }
