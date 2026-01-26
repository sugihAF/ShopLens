"""Product comparison functions for Gemini function calling."""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import register_function
from app.crud.product import product_crud
from app.crud.consensus import consensus_crud


@register_function("compare_products")
async def compare_products(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare multiple products side by side based on reviews and specs.

    Args:
        db: Database session
        args: {product_ids: List[int], aspects?: List[str]}

    Returns:
        Comparison data for all products
    """
    product_ids = args.get("product_ids", [])
    aspects = args.get("aspects")

    if len(product_ids) < 2:
        return {"error": "Need at least 2 products to compare"}
    if len(product_ids) > 5:
        return {"error": "Can compare maximum 5 products at once"}

    comparison_results = []
    all_aspects = set()

    for pid in product_ids:
        product = await product_crud.get(db, id=pid)
        if not product:
            return {"error": f"Product with ID {pid} not found"}

        consensus_list = await consensus_crud.get_by_product(db, product_id=pid)

        # Collect all aspects
        for c in consensus_list:
            all_aspects.add(c.aspect)

        # Build aspect data
        aspect_data = {}
        for c in consensus_list:
            if aspects is None or c.aspect.lower() in [a.lower() for a in aspects]:
                aspect_data[c.aspect] = {
                    "sentiment_score": float(c.average_sentiment),
                    "agreement_score": float(c.agreement_score),
                    "review_count": c.review_count
                }

        comparison_results.append({
            "product_id": pid,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "average_rating": float(product.average_rating) if product.average_rating else None,
            "review_count": product.review_count,
            "specifications": product.specifications or {},
            "aspects": aspect_data
        })

    # Determine which product is best for each aspect
    aspect_winners = {}
    for aspect in (aspects or list(all_aspects)):
        best_product = None
        best_score = -2  # Sentiment ranges from -1 to 1
        for result in comparison_results:
            if aspect in result["aspects"]:
                score = result["aspects"][aspect]["sentiment_score"]
                if score > best_score:
                    best_score = score
                    best_product = result["name"]
        if best_product:
            aspect_winners[aspect] = {
                "winner": best_product,
                "score": best_score
            }

    return {
        "products": comparison_results,
        "aspects_compared": list(aspects) if aspects else list(all_aspects),
        "aspect_winners": aspect_winners,
        "recommendation": _generate_recommendation(comparison_results, aspect_winners)
    }


def _generate_recommendation(
    products: List[Dict[str, Any]],
    aspect_winners: Dict[str, Dict[str, Any]]
) -> str:
    """Generate a simple recommendation based on comparison results."""
    if not products or not aspect_winners:
        return "Unable to generate recommendation due to insufficient data."

    # Count wins per product
    win_counts: Dict[str, int] = {}
    for aspect, winner_data in aspect_winners.items():
        winner = winner_data["winner"]
        win_counts[winner] = win_counts.get(winner, 0) + 1

    if not win_counts:
        return "All products have similar ratings across aspects."

    # Find product with most wins
    best_product = max(win_counts.keys(), key=lambda x: win_counts[x])
    best_count = win_counts[best_product]
    total_aspects = len(aspect_winners)

    if best_count == total_aspects:
        return f"{best_product} leads in all compared aspects."
    elif best_count >= total_aspects / 2:
        # Find what aspects the winner leads in
        winning_aspects = [
            aspect for aspect, data in aspect_winners.items()
            if data["winner"] == best_product
        ]
        return f"{best_product} leads in {', '.join(winning_aspects)}."
    else:
        return "Each product has different strengths - choice depends on priorities."
