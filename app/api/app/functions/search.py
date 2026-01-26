"""Search functions for Gemini function calling."""

import asyncio
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import register_function
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


@register_function("semantic_search")
async def semantic_search(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search across all review content using natural language.
    Uses vector similarity search via Qdrant.

    Args:
        db: Database session
        args: {query: str, limit?: int}

    Returns:
        Semantically similar review content
    """
    query = args.get("query", "")
    limit = min(args.get("limit", 10), 50)

    if not query:
        return {"error": "query is required"}

    try:
        # Try to use vector search if Qdrant is available
        results = await _vector_search(query, limit)
        if results:
            return results
    except Exception as e:
        logger.warning(f"Vector search failed, falling back to text search: {e}")

    # Fallback to text-based search
    return await _text_search(db, query, limit)


async def _vector_search(query: str, limit: int) -> Dict[str, Any]:
    """
    Perform vector similarity search using Qdrant.
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter
        import google.generativeai as genai

        # Generate embedding for query (wrap synchronous call)
        genai.configure(api_key=settings.GEMINI_API_KEY)
        embedding_result = await asyncio.to_thread(
            genai.embed_content,
            model=settings.EMBEDDING_MODEL,
            content=query
        )
        query_vector = embedding_result['embedding']

        # Connect to Qdrant
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )

        # Search (wrap synchronous call)
        search_results = await asyncio.to_thread(
            client.search,
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            with_payload=True
        )

        if not search_results:
            return {
                "query": query,
                "results": [],
                "total": 0,
                "search_type": "vector",
                "message": "No matching content found"
            }

        return {
            "query": query,
            "results": [
                {
                    "score": hit.score,
                    "product_id": hit.payload.get("product_id"),
                    "product_name": hit.payload.get("product_name"),
                    "reviewer_name": hit.payload.get("reviewer_name"),
                    "content": hit.payload.get("content", "")[:500],
                    "aspect": hit.payload.get("aspect"),
                    "review_id": hit.payload.get("review_id"),
                    "source_url": hit.payload.get("source_url")
                }
                for hit in search_results
            ],
            "total": len(search_results),
            "search_type": "vector"
        }

    except ImportError:
        logger.warning("Qdrant client not installed")
        raise
    except Exception as e:
        logger.error(f"Vector search error: {e}")
        raise


async def _text_search(db: AsyncSession, query: str, limit: int) -> Dict[str, Any]:
    """
    Fallback text-based search using PostgreSQL full-text search.
    """
    from sqlalchemy import select, or_, func
    from app.models.review import Review
    from app.models.opinion import Opinion
    from app.models.product import Product

    # Search in reviews
    review_results = await db.execute(
        select(Review, Product)
        .join(Product, Review.product_id == Product.id)
        .where(
            or_(
                Review.content.ilike(f"%{query}%"),
                Review.title.ilike(f"%{query}%")
            )
        )
        .limit(limit)
    )
    reviews = review_results.all()

    # Search in opinions (using quote or summary fields)
    opinion_results = await db.execute(
        select(Opinion, Product)
        .join(Review, Opinion.review_id == Review.id)
        .join(Product, Review.product_id == Product.id)
        .where(
            or_(
                Opinion.quote.ilike(f"%{query}%"),
                Opinion.summary.ilike(f"%{query}%"),
                Opinion.aspect.ilike(f"%{query}%")
            )
        )
        .limit(limit)
    )
    opinions = opinion_results.all()

    results = []

    for review, product in reviews:
        results.append({
            "type": "review",
            "product_id": product.id,
            "product_name": product.name,
            "review_id": review.id,
            "content": review.content[:500] if review.content else None,
            "source_url": review.platform_url
        })

    for opinion, product in opinions:
        results.append({
            "type": "opinion",
            "product_id": product.id,
            "product_name": product.name,
            "aspect": opinion.aspect,
            "content": opinion.quote or opinion.summary,
            "sentiment": float(opinion.sentiment) if opinion.sentiment is not None else None
        })

    return {
        "query": query,
        "results": results[:limit],
        "total": len(results),
        "search_type": "text",
        "note": "Using text-based search. Vector search provides better semantic results when available."
    }
