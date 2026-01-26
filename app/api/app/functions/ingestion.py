"""Ingestion functions for Gemini function calling - YouTube and blog reviews."""

from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.registry import register_function
from app.services.youtube_scraper import youtube_scraper
from app.services.firecrawl_service import get_firecrawl_service
from app.core.logging import get_logger

logger = get_logger(__name__)


@register_function("ingest_youtube_review")
async def ingest_youtube_review(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ingest a YouTube video review into the database.

    This function is called by Gemini when a user provides a YouTube URL
    and wants to add that review to the database.

    Args:
        db: Database session
        args: {video_url: str, product_id?: int}

    Returns:
        Result of the ingestion process
    """
    video_url = args.get("video_url")
    product_id = args.get("product_id")

    if not video_url:
        return {"error": "video_url is required"}

    # Validate URL format
    if not is_valid_youtube_url(video_url):
        return {"error": "Invalid YouTube URL format. Please provide a valid YouTube video URL."}

    try:
        result = await youtube_scraper.ingest_youtube_review(
            db=db,
            video_url=video_url,
            product_id=product_id
        )

        if result.get("status") == "success":
            return {
                "success": True,
                "message": result.get("message"),
                "review_id": result.get("review_id"),
                "product_id": result.get("product_id"),
                "product_name": result.get("product_name"),
                "summary": result.get("summary"),
                "opinions_extracted": result.get("opinions_count", 0)
            }
        elif result.get("status") == "exists":
            return {
                "success": True,
                "message": "This review has already been ingested",
                "review_id": result.get("review_id"),
                "already_exists": True
            }
        else:
            return {
                "success": False,
                "error": result.get("message", "Failed to ingest review"),
                "details": result
            }

    except ValueError as e:
        return {"error": str(e)}
    except RuntimeError as e:
        logger.error(f"Runtime error in YouTube ingestion: {e}")
        return {"error": f"Service not available: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in YouTube ingestion: {e}", exc_info=True)
        return {"error": f"Failed to ingest YouTube review: {str(e)}"}


def is_valid_youtube_url(url: str) -> bool:
    """Check if the URL is a valid YouTube URL."""
    import re

    youtube_patterns = [
        r'^https?://(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'^https?://(www\.)?youtube\.com/v/[\w-]+',
        r'^https?://youtu\.be/[\w-]+',
        r'^https?://(www\.)?youtube\.com/embed/[\w-]+',
        r'^https?://(www\.)?youtube\.com/shorts/[\w-]+',
    ]

    for pattern in youtube_patterns:
        if re.match(pattern, url, re.IGNORECASE):
            return True

    return False


@register_function("ingest_blog_review")
async def ingest_blog_review(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ingest a blog review from a URL.

    This function scrapes a tech blog review URL using Firecrawl,
    extracts structured review data using Gemini, and stores it
    in the database.

    Args:
        db: Database session
        args: {url: str, product_id?: int}

    Returns:
        Dictionary with ingestion results
    """
    url = args.get("url")
    product_id = args.get("product_id")

    if not url:
        return {"error": "url is required"}

    # Validate URL format
    if not url.startswith(("http://", "https://")):
        return {"error": "Invalid URL format. URL must start with http:// or https://"}

    try:
        firecrawl_service = get_firecrawl_service()
        result = await firecrawl_service.ingest_blog_review(
            db=db,
            url=url,
            product_id=product_id
        )

        # Handle different status cases
        if result.get("status") == "already_exists":
            return {
                "success": True,
                "already_existed": True,
                "review_id": result.get("review_id"),
                "message": result.get("message")
            }
        elif result.get("status") == "error":
            return {
                "success": False,
                "error": result.get("message")
            }
        else:
            return {
                "success": True,
                "already_existed": False,
                "review_id": result.get("review_id"),
                "product_id": result.get("product_id"),
                "reviewer_id": result.get("reviewer_id"),
                "product_name": result.get("product_name"),
                "reviewer_name": result.get("reviewer_name"),
                "opinions_created": result.get("opinions_created"),
                "summary": result.get("summary"),
                "message": result.get("message")
            }

    except RuntimeError as e:
        # Handle configuration errors
        logger.error(f"Firecrawl ingestion runtime error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Firecrawl ingestion unexpected error: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to ingest blog review: {str(e)}"
        }
