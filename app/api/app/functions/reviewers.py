"""Reviewer functions for Gemini function calling."""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import register_function
from app.crud.reviewer import reviewer_crud


@register_function("get_reviewer_info")
async def get_reviewer_info(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get information about a specific tech reviewer.

    Args:
        db: Database session
        args: {reviewer_id: int}

    Returns:
        Reviewer information
    """
    reviewer_id = args.get("reviewer_id")
    if not reviewer_id:
        return {"error": "reviewer_id is required"}

    reviewer = await reviewer_crud.get(db, id=reviewer_id)

    if not reviewer:
        return {"error": f"Reviewer with ID {reviewer_id} not found"}

    # Get stats from the stats JSONB field
    stats = reviewer.stats or {}

    return {
        "id": reviewer.id,
        "name": reviewer.name,
        "platform": reviewer.platform.value if reviewer.platform else None,
        "channel_name": reviewer.name,  # Using name as channel_name
        "channel_url": reviewer.profile_url,
        "subscriber_count": reviewer.subscriber_count,
        "total_views": stats.get('total_views'),
        "country": stats.get('country'),
        "language": stats.get('language'),
        "expertise": stats.get('typical_categories', []),
        "description": reviewer.description,
        "trust_score": float(reviewer.credibility_score) if reviewer.credibility_score else None,
        "review_count": reviewer.total_reviews,
        "average_rating_given": stats.get('average_rating_given'),
        "metadata": stats
    }
