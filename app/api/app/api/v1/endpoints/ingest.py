"""Ingestion endpoints for YouTube and blog reviews."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.youtube_scraper import youtube_scraper
from app.services.firecrawl_service import get_firecrawl_service
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


# Request/Response schemas
class YouTubeIngestRequest(BaseModel):
    """Request schema for YouTube video ingestion."""
    video_url: str
    product_id: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "product_id": None
            }
        }


class BlogIngestRequest(BaseModel):
    """Request schema for blog review ingestion."""
    url: str
    product_id: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.theverge.com/reviews/product-review",
                "product_id": None
            }
        }


class IngestResponse(BaseModel):
    """Response schema for ingestion operations."""
    success: bool
    message: str
    review_id: Optional[int] = None
    reviewer_id: Optional[int] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    reviewer_name: Optional[str] = None
    summary: Optional[str] = None
    opinions_count: Optional[int] = None
    already_exists: Optional[bool] = None


class IngestErrorResponse(BaseModel):
    """Error response schema for ingestion operations."""
    success: bool = False
    error: str
    details: Optional[dict] = None


@router.post(
    "/youtube",
    response_model=IngestResponse,
    responses={
        400: {"model": IngestErrorResponse, "description": "Invalid request"},
        500: {"model": IngestErrorResponse, "description": "Ingestion failed"},
        503: {"model": IngestErrorResponse, "description": "Service unavailable"}
    },
    summary="Ingest YouTube Review",
    description="""
    Ingest a YouTube video review into the database.

    This endpoint will:
    1. Use Gemini with Google Search grounding to scrape the YouTube video metadata
    2. Extract video transcript content using AI
    3. Analyze and extract structured review data (product, pros, cons, opinions)
    4. Create or link to existing Reviewer and Product records
    5. Store the Review and extracted Opinions

    **Note**: This operation may take 10-30 seconds as it involves AI processing.
    """
)
async def ingest_youtube_review(
    request: YouTubeIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest a YouTube video review.

    Extracts video metadata, transcript content, and structures it into
    reviewer/review/opinion records in the database.
    """
    # Validate URL format
    if not _is_valid_youtube_url(request.video_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube URL format. Please provide a valid YouTube video URL."
        )

    try:
        result = await youtube_scraper.ingest_youtube_review(
            db=db,
            video_url=request.video_url,
            product_id=request.product_id
        )

        if result.get("status") == "success":
            return IngestResponse(
                success=True,
                message=result.get("message", "Review ingested successfully"),
                review_id=result.get("review_id"),
                reviewer_id=result.get("reviewer_id"),
                product_id=result.get("product_id"),
                product_name=result.get("product_name"),
                summary=result.get("summary"),
                opinions_count=result.get("opinions_count"),
                already_exists=False
            )
        elif result.get("status") == "exists":
            return IngestResponse(
                success=True,
                message="Review already exists in the database",
                review_id=result.get("review_id"),
                already_exists=True
            )
        else:
            # Ingestion failed
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to ingest review")
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        logger.error(f"Runtime error during YouTube ingestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ingestion service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during YouTube ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during ingestion"
        )


@router.post(
    "/blog",
    response_model=IngestResponse,
    responses={
        400: {"model": IngestErrorResponse, "description": "Invalid request"},
        500: {"model": IngestErrorResponse, "description": "Ingestion failed"},
        503: {"model": IngestErrorResponse, "description": "Service unavailable"}
    },
    summary="Ingest Blog Review",
    description="""
    Ingest a blog review from a URL into the database.

    This endpoint will:
    1. Scrape the blog article content using Firecrawl
    2. Use Gemini to extract structured review data (product, pros, cons, opinions)
    3. Create or link to existing Reviewer and Product records
    4. Store the Review and extracted Opinions

    **Note**: This operation requires FIRECRAWL_API_KEY to be configured.
    If product_id is not provided, the system will try to match the product by name.
    """
)
async def ingest_blog_review(
    request: BlogIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest a blog review.

    Scrapes the blog URL using Firecrawl, extracts structured data using Gemini,
    and stores it in the database.
    """
    # Validate URL format
    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL format. URL must start with http:// or https://"
        )

    try:
        firecrawl_service = get_firecrawl_service()
        result = await firecrawl_service.ingest_blog_review(
            db=db,
            url=request.url,
            product_id=request.product_id
        )

        if result.get("status") == "success":
            return IngestResponse(
                success=True,
                message=result.get("message", "Review ingested successfully"),
                review_id=result.get("review_id"),
                reviewer_id=result.get("reviewer_id"),
                product_id=result.get("product_id"),
                product_name=result.get("product_name"),
                reviewer_name=result.get("reviewer_name"),
                summary=result.get("summary"),
                opinions_count=result.get("opinions_created"),
                already_exists=False
            )
        elif result.get("status") == "already_exists":
            return IngestResponse(
                success=True,
                message=result.get("message", "Review already exists"),
                review_id=result.get("review_id"),
                already_exists=True
            )
        else:
            # Ingestion failed
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to ingest review")
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        logger.error(f"Runtime error during blog ingestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ingestion service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during blog ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during ingestion"
        )


def _is_valid_youtube_url(url: str) -> bool:
    """Validate YouTube URL format."""
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
