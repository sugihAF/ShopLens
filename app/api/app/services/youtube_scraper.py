"""YouTube scraper service using Gemini with Google Search grounding."""

import re
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging import get_logger
from app.models.reviewer import Reviewer, Platform
from app.models.review import Review, ReviewType, ProcessingStatus
from app.models.opinion import Opinion
from app.crud.reviewer import reviewer_crud
from app.crud.review import review_crud
from app.crud.product import product_crud

logger = get_logger(__name__)


class YouTubeScraperService:
    """
    Service for scraping YouTube video reviews using Gemini with Google Search grounding.

    Uses Gemini's agentic capabilities to:
    1. Browse/search for YouTube video information
    2. Extract video metadata and transcript content
    3. Analyze and structure review data
    """

    def __init__(self):
        """Initialize the scraper with Gemini model configured for grounding."""
        self.client = None
        self._init_gemini()

    def _init_gemini(self):
        """Initialize Gemini client for scraping and analysis."""
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set - YouTube scraper will not work")
            return

        try:
            # Initialize the new genai client
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("YouTube scraper Gemini client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Gemini client for scraper: {e}", exc_info=True)
            self.client = None

    def _extract_video_id(self, video_url: str) -> Optional[str]:
        """Extract YouTube video ID from various URL formats."""
        # Handle different YouTube URL formats
        patterns = [
            r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'(?:embed/)([a-zA-Z0-9_-]{11})',
            r'(?:watch\?.*v=)([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)

        return None

    async def scrape_youtube_video(self, video_url: str) -> Dict[str, Any]:
        """
        Scrape YouTube video information using Gemini with Google Search grounding.

        Args:
            video_url: URL of the YouTube video to scrape

        Returns:
            Dictionary containing video metadata and transcript content
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized. Check GEMINI_API_KEY.")

        video_id = self._extract_video_id(video_url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {video_url}")

        logger.info(f"Scraping YouTube video: {video_id}")

        # Prompt for Gemini to search and extract video information
        scrape_prompt = f"""
Search for information about this YouTube video: {video_url}

I need you to find and provide the following information:
1. Video title
2. Channel name (the YouTube channel that uploaded this video)
3. Channel URL
4. Approximate view count (if available)
5. Approximate like count (if available)
6. Publish date or upload date
7. Video description summary
8. Video duration (if available)

Additionally, search for the transcript or detailed content summary of this video. If this is a tech product review, I need:
- What product(s) are being reviewed
- Key points discussed in the video
- Any ratings or recommendations given

Please provide the information in a structured format. If you cannot find specific information, indicate that it was not found.

Format your response as JSON with the following structure:
{{
    "video_id": "{video_id}",
    "title": "...",
    "channel_name": "...",
    "channel_url": "...",
    "channel_id": "...",  // Extract from channel URL if possible
    "view_count": number or null,
    "like_count": number or null,
    "publish_date": "YYYY-MM-DD" or null,
    "duration_seconds": number or null,
    "description_summary": "...",
    "transcript_summary": "...",  // Summary of the video content
    "products_mentioned": ["product1", "product2"],
    "key_points": ["point1", "point2", ...],
    "recommendation": "positive/negative/neutral/mixed" or null,
    "raw_content": "..."  // Any detailed transcript or content you can find
}}
"""

        try:
            # Use the new SDK with Google Search grounding
            response = await self.client.aio.models.generate_content(
                model=settings.LLM_MODEL,
                contents=scrape_prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            response_text = response.text

            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                video_data = json.loads(json_match.group())
            else:
                # If no JSON found, create a basic structure from the response
                video_data = {
                    "video_id": video_id,
                    "title": None,
                    "channel_name": None,
                    "channel_url": None,
                    "channel_id": None,
                    "view_count": None,
                    "like_count": None,
                    "publish_date": None,
                    "duration_seconds": None,
                    "description_summary": None,
                    "transcript_summary": response_text,
                    "products_mentioned": [],
                    "key_points": [],
                    "recommendation": None,
                    "raw_content": response_text
                }

            # Ensure video_id is set
            video_data["video_id"] = video_id
            video_data["platform_url"] = video_url

            logger.info(f"Successfully scraped video: {video_data.get('title', 'Unknown')}")
            return video_data

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            return {
                "video_id": video_id,
                "platform_url": video_url,
                "title": None,
                "channel_name": None,
                "raw_content": response_text if 'response_text' in locals() else None,
                "error": "Failed to parse structured data"
            }
        except Exception as e:
            logger.error(f"Error scraping YouTube video: {e}", exc_info=True)
            raise

    async def extract_review_data(self, video_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze video transcript/content and extract structured review data.

        Args:
            video_content: Dictionary from scrape_youtube_video containing video info

        Returns:
            Structured review data with product info, ratings, pros, cons, and opinions
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized.")

        # Combine available content for analysis
        content_parts = []
        if video_content.get("title"):
            content_parts.append(f"Title: {video_content['title']}")
        if video_content.get("description_summary"):
            content_parts.append(f"Description: {video_content['description_summary']}")
        if video_content.get("transcript_summary"):
            content_parts.append(f"Content Summary: {video_content['transcript_summary']}")
        if video_content.get("raw_content"):
            content_parts.append(f"Full Content: {video_content['raw_content']}")
        if video_content.get("key_points"):
            content_parts.append(f"Key Points: {', '.join(video_content['key_points'])}")

        content_text = "\n\n".join(content_parts)

        if not content_text.strip():
            return {
                "error": "No content available for analysis",
                "product_name": None,
                "overall_rating": None,
                "recommendation": None,
                "pros": [],
                "cons": [],
                "opinions": []
            }

        analysis_prompt = f"""
Analyze the following tech product review content and extract structured information.

CONTENT:
{content_text}

Please analyze this review and provide:
1. Product name being reviewed (be specific with model numbers if mentioned)
2. Overall rating or score (convert to 0-10 scale if possible)
3. Overall recommendation (buy/don't buy/conditional)
4. List of pros (positive points)
5. List of cons (negative points)
6. Detailed opinions by aspect (camera, battery, display, performance, build quality, value, software, etc.)

For each opinion, provide:
- aspect: The product aspect being discussed
- sentiment: A score from -1.0 (very negative) to 1.0 (very positive)
- confidence: How confident you are in this extraction (0.0 to 1.0)
- quote: A relevant quote or paraphrase from the content
- summary: Brief summary of the opinion

Also determine the review type:
- full_review: Complete, detailed review
- quick_look: Brief first impressions
- comparison: Comparing multiple products
- long_term: Long-term usage review
- unboxing: Unboxing video

Format your response as JSON:
{{
    "product_name": "...",
    "product_brand": "...",
    "product_category": "smartphones/laptops/headphones/tablets/smartwatches/cameras/monitors/keyboards/mice/other",
    "overall_rating": number (0-10) or null,
    "recommendation": "buy/conditional_buy/dont_buy/neutral",
    "review_type": "full_review/quick_look/comparison/long_term/unboxing",
    "summary": "2-3 sentence summary of the review",
    "pros": ["pro1", "pro2", ...],
    "cons": ["con1", "con2", ...],
    "opinions": [
        {{
            "aspect": "camera",
            "sentiment": 0.8,
            "confidence": 0.9,
            "quote": "...",
            "summary": "..."
        }},
        ...
    ]
}}
"""

        try:
            # Use the new SDK for analysis (no grounding needed)
            response = await self.client.aio.models.generate_content(
                model=settings.LLM_MODEL,
                contents=analysis_prompt
            )
            response_text = response.text

            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                review_data = json.loads(json_match.group())
            else:
                review_data = {
                    "error": "Failed to extract structured review data",
                    "raw_analysis": response_text
                }

            logger.info(f"Extracted review data for product: {review_data.get('product_name', 'Unknown')}")
            return review_data

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse review analysis JSON: {e}")
            return {
                "error": "Failed to parse review analysis",
                "raw_analysis": response_text if 'response_text' in locals() else None
            }
        except Exception as e:
            logger.error(f"Error extracting review data: {e}", exc_info=True)
            raise

    async def ingest_youtube_review(
        self,
        db: AsyncSession,
        video_url: str,
        product_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Full ingestion pipeline: scrape video, extract review data, and save to database.

        Args:
            db: Database session
            video_url: URL of the YouTube video
            product_id: Optional product ID if already known

        Returns:
            Dictionary containing the created Review and related data
        """
        logger.info(f"Starting YouTube review ingestion for: {video_url}")

        # Check if review already exists
        existing_review = await review_crud.get_by_platform_url(db, video_url)
        if existing_review:
            logger.info(f"Review already exists for URL: {video_url}")
            return {
                "status": "exists",
                "message": "Review already ingested",
                "review_id": existing_review.id
            }

        # Step 1: Scrape video information
        video_content = await self.scrape_youtube_video(video_url)

        if video_content.get("error"):
            logger.warning(f"Scraping returned error: {video_content['error']}")

        # Step 2: Extract structured review data
        review_data = await self.extract_review_data(video_content)

        if review_data.get("error") and not review_data.get("product_name"):
            return {
                "status": "error",
                "message": f"Failed to extract review data: {review_data.get('error')}",
                "video_content": video_content
            }

        # Step 3: Create or get Reviewer
        reviewer = await self._get_or_create_reviewer(db, video_content)

        # Step 4: Get or create Product if not provided
        if not product_id and review_data.get("product_name"):
            product = await self._get_or_create_product(db, review_data)
            product_id = product.id if product else None

        if not product_id:
            return {
                "status": "error",
                "message": "Could not determine product for review",
                "video_content": video_content,
                "review_data": review_data
            }

        # Step 5: Create Review record
        review = await self._create_review(
            db,
            video_content,
            review_data,
            reviewer.id,
            product_id
        )

        # Step 6: Create Opinion records
        opinions = await self._create_opinions(db, review.id, review_data.get("opinions", []))

        # Step 7: Update reviewer stats
        await self._update_reviewer_stats(db, reviewer)

        # Step 8: Update product review count
        await self._update_product_stats(db, product_id)

        # Commit all changes
        await db.commit()

        logger.info(f"Successfully ingested review {review.id} for product {product_id}")

        return {
            "status": "success",
            "message": "Review ingested successfully",
            "review_id": review.id,
            "reviewer_id": reviewer.id,
            "product_id": product_id,
            "product_name": review_data.get("product_name"),
            "opinions_count": len(opinions),
            "summary": review_data.get("summary")
        }

    async def _get_or_create_reviewer(
        self,
        db: AsyncSession,
        video_content: Dict[str, Any]
    ) -> Reviewer:
        """Get existing reviewer or create a new one."""
        channel_id = video_content.get("channel_id")
        channel_name = video_content.get("channel_name", "Unknown Channel")
        channel_url = video_content.get("channel_url")

        # Generate a platform_id from channel info
        if channel_id:
            platform_id = channel_id
        elif channel_url:
            # Extract ID from URL if possible
            platform_id = channel_url.rstrip("/").split("/")[-1]
        else:
            # Use channel name as fallback (not ideal but functional)
            platform_id = channel_name.lower().replace(" ", "_")

        # Check if reviewer exists
        existing_reviewer = await reviewer_crud.get_by_platform_id(db, platform_id)
        if existing_reviewer:
            return existing_reviewer

        # Create new reviewer
        reviewer = Reviewer(
            name=channel_name,
            platform=Platform.YOUTUBE,
            platform_id=platform_id,
            profile_url=channel_url,
            description=f"YouTube tech reviewer - {channel_name}",
            credibility_score=0.5,  # Default score for new reviewers
            is_active=True,
            is_verified=False,
            stats={}
        )

        db.add(reviewer)
        await db.flush()
        await db.refresh(reviewer)

        logger.info(f"Created new reviewer: {reviewer.name} (ID: {reviewer.id})")
        return reviewer

    async def _get_or_create_product(
        self,
        db: AsyncSession,
        review_data: Dict[str, Any]
    ):
        """Get existing product or create a new one based on review data."""
        from app.models.product import Product

        product_name = review_data.get("product_name")
        if not product_name:
            return None

        # Search for existing product
        products = await product_crud.search(db, query=product_name, limit=1)
        if products:
            return products[0]

        # Create new product
        product = Product(
            name=product_name,
            brand=review_data.get("product_brand"),
            category=review_data.get("product_category", "other"),
            description=review_data.get("summary"),
            specifications={},
            review_count=0,
            average_rating=None
        )

        db.add(product)
        await db.flush()
        await db.refresh(product)

        logger.info(f"Created new product: {product.name} (ID: {product.id})")
        return product

    async def _create_review(
        self,
        db: AsyncSession,
        video_content: Dict[str, Any],
        review_data: Dict[str, Any],
        reviewer_id: int,
        product_id: int
    ) -> Review:
        """Create a new Review record."""
        # Parse publish date
        publish_date = None
        if video_content.get("publish_date"):
            try:
                publish_date = datetime.fromisoformat(video_content["publish_date"])
            except (ValueError, TypeError):
                pass

        # Map review type
        review_type_map = {
            "full_review": ReviewType.FULL_REVIEW,
            "quick_look": ReviewType.QUICK_LOOK,
            "comparison": ReviewType.COMPARISON,
            "long_term": ReviewType.LONG_TERM,
            "unboxing": ReviewType.UNBOXING
        }
        review_type = review_type_map.get(
            review_data.get("review_type", "full_review"),
            ReviewType.FULL_REVIEW
        )

        # Build content from available data
        content_parts = []
        if review_data.get("summary"):
            content_parts.append(review_data["summary"])
        if review_data.get("pros"):
            content_parts.append(f"Pros: {', '.join(review_data['pros'])}")
        if review_data.get("cons"):
            content_parts.append(f"Cons: {', '.join(review_data['cons'])}")
        if video_content.get("transcript_summary"):
            content_parts.append(video_content["transcript_summary"])

        content = "\n\n".join(content_parts) if content_parts else "Review content pending"

        review = Review(
            product_id=product_id,
            reviewer_id=reviewer_id,
            title=video_content.get("title"),
            content=content,
            summary=review_data.get("summary"),
            platform_url=video_content.get("platform_url"),
            video_id=video_content.get("video_id"),
            review_type=review_type,
            overall_rating=review_data.get("overall_rating"),
            review_metadata={
                "duration_seconds": video_content.get("duration_seconds"),
                "view_count": video_content.get("view_count"),
                "like_count": video_content.get("like_count"),
                "recommendation": review_data.get("recommendation"),
                "pros": review_data.get("pros", []),
                "cons": review_data.get("cons", [])
            },
            is_processed=True,
            processing_status=ProcessingStatus.COMPLETED,
            published_at=publish_date,
            processed_at=datetime.now(timezone.utc)
        )

        db.add(review)
        await db.flush()
        await db.refresh(review)

        logger.info(f"Created review: {review.id} for product {product_id}")
        return review

    async def _create_opinions(
        self,
        db: AsyncSession,
        review_id: int,
        opinions_data: List[Dict[str, Any]]
    ) -> List[Opinion]:
        """Create Opinion records from extracted opinions."""
        opinions = []

        for opinion_data in opinions_data:
            opinion = Opinion(
                review_id=review_id,
                aspect=opinion_data.get("aspect", "general"),
                sentiment=float(opinion_data.get("sentiment", 0.0)),
                confidence=float(opinion_data.get("confidence", 0.5)),
                quote=opinion_data.get("quote"),
                summary=opinion_data.get("summary")
            )
            db.add(opinion)
            opinions.append(opinion)

        if opinions:
            await db.flush()
            logger.info(f"Created {len(opinions)} opinions for review {review_id}")

        return opinions

    async def _update_reviewer_stats(self, db: AsyncSession, reviewer: Reviewer):
        """Update reviewer's total review count."""
        from sqlalchemy import select, func

        result = await db.execute(
            select(func.count()).where(Review.reviewer_id == reviewer.id)
        )
        review_count = result.scalar() or 0

        reviewer.total_reviews = review_count
        db.add(reviewer)

    async def _update_product_stats(self, db: AsyncSession, product_id: int):
        """Update product's review count and average rating."""
        from sqlalchemy import select, func
        from app.models.product import Product

        # Get review count
        count_result = await db.execute(
            select(func.count()).where(Review.product_id == product_id)
        )
        review_count = count_result.scalar() or 0

        # Get average rating
        avg_result = await db.execute(
            select(func.avg(Review.overall_rating))
            .where(Review.product_id == product_id)
            .where(Review.overall_rating.isnot(None))
        )
        avg_rating = avg_result.scalar()

        # Update product
        product = await product_crud.get(db, id=product_id)
        if product:
            product.review_count = review_count
            product.average_rating = float(avg_rating) if avg_rating else None
            db.add(product)


# Singleton instance
youtube_scraper = YouTubeScraperService()
