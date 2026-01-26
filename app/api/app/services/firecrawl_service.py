"""Firecrawl service for scraping tech blog reviews."""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from firecrawl import FirecrawlApp
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging import get_logger
from app.models.reviewer import Reviewer, Platform
from app.models.review import Review, ReviewType, ProcessingStatus
from app.models.opinion import Opinion
from app.models.product import Product

logger = get_logger(__name__)

# Gemini prompt for extracting structured review data from blog content
EXTRACTION_PROMPT = """You are an expert at extracting structured data from tech product reviews.

Analyze the following blog post content and extract the review information in a structured JSON format.

IMPORTANT: Only extract information that is explicitly stated in the content. Do not make up or infer data.

Return a JSON object with this structure:
{
    "product_name": "Full product name being reviewed (e.g., 'iPhone 15 Pro Max')",
    "product_brand": "Brand name (e.g., 'Apple')",
    "product_category": "Category: smartphones, laptops, headphones, tablets, smartwatches, cameras, monitors, keyboards, mice, or other",
    "reviewer_name": "Name of the reviewer or publication",
    "reviewer_description": "Brief description of the reviewer/publication if available",
    "review_title": "Title of the review article",
    "overall_rating": null or a number from 0-10 if explicitly stated,
    "summary": "A 2-3 sentence summary of the overall verdict",
    "pros": ["List of positive points mentioned"],
    "cons": ["List of negative points mentioned"],
    "opinions": [
        {
            "aspect": "The aspect being discussed (e.g., camera, battery, display, performance, build_quality, software, value)",
            "sentiment": "A number from -1.0 (very negative) to 1.0 (very positive)",
            "confidence": "A number from 0.0 to 1.0 indicating how clear the opinion was",
            "quote": "A direct quote from the review that supports this opinion (keep it short)",
            "summary": "A one-sentence summary of the opinion"
        }
    ]
}

If you cannot determine certain fields, use null for optional fields or empty arrays for lists.

Blog post content:
---
{content}
---

Return ONLY the JSON object, no additional text."""


class FirecrawlService:
    """
    Service for scraping tech blog reviews using Firecrawl.

    Handles:
    - Scraping blog URLs with Firecrawl
    - Extracting structured review data using Gemini
    - Creating/updating database records for reviews
    """

    def __init__(self):
        """Initialize Firecrawl and Gemini clients."""
        self.firecrawl_client = None
        self.genai_client = None
        self._init_clients()

    def _init_clients(self):
        """Initialize API clients."""
        # Initialize Firecrawl
        if settings.FIRECRAWL_API_KEY:
            try:
                self.firecrawl_client = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
                logger.info("Firecrawl client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Firecrawl client: {e}")
        else:
            logger.warning("FIRECRAWL_API_KEY not set - blog scraping will not work")

        # Initialize Gemini client for extraction
        if settings.GEMINI_API_KEY:
            try:
                self.genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Gemini client initialized for extraction")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
        else:
            logger.warning("GEMINI_API_KEY not set - extraction will not work")

    async def scrape_blog_review(self, url: str) -> Dict[str, Any]:
        """
        Scrape a blog review URL and extract structured data.

        Args:
            url: URL of the blog review to scrape

        Returns:
            Dictionary with extracted review data

        Raises:
            RuntimeError: If clients are not initialized or scraping fails
        """
        if not self.firecrawl_client:
            raise RuntimeError(
                "Firecrawl client not initialized. Please set FIRECRAWL_API_KEY."
            )

        if not self.genai_client:
            raise RuntimeError(
                "Gemini client not initialized. Please set GEMINI_API_KEY."
            )

        logger.info(f"Scraping blog review from: {url}")

        # Step 1: Scrape the URL with Firecrawl
        try:
            scrape_result = self.firecrawl_client.scrape_url(
                url,
                params={
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                }
            )
        except Exception as e:
            logger.error(f"Firecrawl scraping failed for {url}: {e}")
            raise RuntimeError(f"Failed to scrape URL: {str(e)}")

        if not scrape_result or not scrape_result.get("markdown"):
            raise RuntimeError("Firecrawl returned empty content")

        content = scrape_result["markdown"]
        metadata = scrape_result.get("metadata", {})

        logger.info(f"Scraped {len(content)} characters from {url}")

        # Step 2: Extract structured data using Gemini
        try:
            extraction_prompt = EXTRACTION_PROMPT.format(content=content[:50000])  # Limit content size
            response = await self.genai_client.aio.models.generate_content(
                model=settings.LLM_MODEL,
                contents=extraction_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for extraction
                    top_p=0.95,
                    max_output_tokens=4096,
                )
            )

            # Parse the JSON response
            response_text = response.text.strip()
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            extracted_data = json.loads(response_text.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini extraction response: {e}")
            raise RuntimeError(f"Failed to extract structured data: Invalid JSON response")
        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
            raise RuntimeError(f"Failed to extract structured data: {str(e)}")

        # Add source metadata
        extracted_data["source_url"] = url
        extracted_data["source_title"] = metadata.get("title", "")
        extracted_data["scraped_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Successfully extracted review data for: {extracted_data.get('product_name', 'Unknown')}")

        return extracted_data

    async def ingest_blog_review(
        self,
        db: AsyncSession,
        url: str,
        product_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Ingest a blog review from URL into the database.

        This method:
        1. Scrapes the blog URL
        2. Extracts structured data using Gemini
        3. Creates/updates Reviewer if needed
        4. Creates/finds Product if needed
        5. Creates Review record
        6. Creates Opinion records

        Args:
            db: Database session
            url: URL of the blog review
            product_id: Optional product ID if already known

        Returns:
            Dictionary with created record IDs and summary
        """
        # Check for existing review with this URL
        existing_review = await db.execute(
            select(Review).where(Review.platform_url == url)
        )
        existing = existing_review.scalar_one_or_none()
        if existing:
            return {
                "status": "already_exists",
                "review_id": existing.id,
                "message": f"Review from this URL already exists (ID: {existing.id})"
            }

        # Scrape and extract data
        extracted_data = await self.scrape_blog_review(url)

        # Step 1: Find or create reviewer
        reviewer = await self._get_or_create_reviewer(db, extracted_data)

        # Step 2: Find or create product
        product = await self._get_or_find_product(db, product_id, extracted_data)
        if not product:
            return {
                "status": "error",
                "message": f"Could not find or create product: {extracted_data.get('product_name', 'Unknown')}. Please create the product first or provide a product_id."
            }

        # Step 3: Create review
        review = await self._create_review(db, product, reviewer, extracted_data, url)

        # Step 4: Create opinions
        opinions_created = await self._create_opinions(db, review, extracted_data)

        # Step 5: Update product stats
        await self._update_product_stats(db, product)

        # Commit all changes
        await db.commit()

        logger.info(
            f"Successfully ingested review: product={product.name}, "
            f"reviewer={reviewer.name}, opinions={opinions_created}"
        )

        return {
            "status": "success",
            "review_id": review.id,
            "product_id": product.id,
            "reviewer_id": reviewer.id,
            "opinions_created": opinions_created,
            "product_name": product.name,
            "reviewer_name": reviewer.name,
            "summary": extracted_data.get("summary", ""),
            "message": f"Successfully ingested review for {product.name} by {reviewer.name}"
        }

    async def _get_or_create_reviewer(
        self,
        db: AsyncSession,
        extracted_data: Dict[str, Any]
    ) -> Reviewer:
        """Get existing reviewer or create a new one."""
        reviewer_name = extracted_data.get("reviewer_name", "Unknown Blog")
        source_url = extracted_data.get("source_url", "")

        # Generate a platform_id from the domain
        from urllib.parse import urlparse
        parsed_url = urlparse(source_url)
        platform_id = f"blog:{parsed_url.netloc}"

        # Check for existing reviewer
        result = await db.execute(
            select(Reviewer).where(Reviewer.platform_id == platform_id)
        )
        reviewer = result.scalar_one_or_none()

        if reviewer:
            return reviewer

        # Create new reviewer
        reviewer = Reviewer(
            name=reviewer_name,
            platform=Platform.BLOG,
            platform_id=platform_id,
            profile_url=f"https://{parsed_url.netloc}",
            description=extracted_data.get("reviewer_description", ""),
            credibility_score=0.5,  # Default score for new bloggers
            total_reviews=1,
            is_active=True,
            is_verified=False,
        )
        db.add(reviewer)
        await db.flush()  # Get the ID

        logger.info(f"Created new reviewer: {reviewer.name} (ID: {reviewer.id})")
        return reviewer

    async def _get_or_find_product(
        self,
        db: AsyncSession,
        product_id: Optional[int],
        extracted_data: Dict[str, Any]
    ) -> Optional[Product]:
        """Get product by ID or try to find by name."""
        # If product_id provided, use it
        if product_id:
            result = await db.execute(
                select(Product).where(Product.id == product_id)
            )
            product = result.scalar_one_or_none()
            if product:
                return product
            logger.warning(f"Product ID {product_id} not found")

        # Try to find by name
        product_name = extracted_data.get("product_name")
        if product_name:
            result = await db.execute(
                select(Product).where(Product.name.ilike(f"%{product_name}%"))
            )
            product = result.scalar_one_or_none()
            if product:
                logger.info(f"Found existing product: {product.name} (ID: {product.id})")
                return product

        # Product not found - we could create it, but better to require explicit product
        # This prevents creating duplicate products with slightly different names
        logger.warning(f"Product not found: {product_name}")
        return None

    async def _create_review(
        self,
        db: AsyncSession,
        product: Product,
        reviewer: Reviewer,
        extracted_data: Dict[str, Any],
        url: str
    ) -> Review:
        """Create a new review record."""
        # Build summary from pros/cons if no summary provided
        summary = extracted_data.get("summary", "")
        if not summary:
            pros = extracted_data.get("pros", [])
            cons = extracted_data.get("cons", [])
            if pros or cons:
                summary_parts = []
                if pros:
                    summary_parts.append(f"Pros: {', '.join(pros[:3])}")
                if cons:
                    summary_parts.append(f"Cons: {', '.join(cons[:3])}")
                summary = ". ".join(summary_parts)

        # Build content from pros, cons, and opinions
        content_parts = []
        if extracted_data.get("summary"):
            content_parts.append(f"Summary: {extracted_data['summary']}")
        if extracted_data.get("pros"):
            content_parts.append(f"Pros: {', '.join(extracted_data['pros'])}")
        if extracted_data.get("cons"):
            content_parts.append(f"Cons: {', '.join(extracted_data['cons'])}")

        content = "\n\n".join(content_parts) if content_parts else "Review content extracted from blog."

        review = Review(
            product_id=product.id,
            reviewer_id=reviewer.id,
            title=extracted_data.get("review_title", extracted_data.get("source_title", "")),
            content=content,
            summary=summary,
            platform_url=url,
            review_type=ReviewType.FULL_REVIEW,
            overall_rating=extracted_data.get("overall_rating"),
            review_metadata={
                "pros": extracted_data.get("pros", []),
                "cons": extracted_data.get("cons", []),
                "source_title": extracted_data.get("source_title", ""),
                "scraped_at": extracted_data.get("scraped_at", ""),
            },
            is_processed=True,
            processing_status=ProcessingStatus.COMPLETED,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(review)
        await db.flush()  # Get the ID

        logger.info(f"Created review ID: {review.id}")
        return review

    async def _create_opinions(
        self,
        db: AsyncSession,
        review: Review,
        extracted_data: Dict[str, Any]
    ) -> int:
        """Create opinion records from extracted data."""
        opinions = extracted_data.get("opinions", [])
        created_count = 0

        for opinion_data in opinions:
            aspect = opinion_data.get("aspect", "").lower()
            if not aspect:
                continue

            # Normalize aspect names
            aspect_mapping = {
                "camera": "camera",
                "battery": "battery",
                "display": "display",
                "screen": "display",
                "performance": "performance",
                "speed": "performance",
                "build": "build_quality",
                "build_quality": "build_quality",
                "design": "build_quality",
                "software": "software",
                "value": "value",
                "price": "value",
                "sound": "audio",
                "audio": "audio",
                "speaker": "audio",
            }
            normalized_aspect = aspect_mapping.get(aspect, aspect)

            opinion = Opinion(
                review_id=review.id,
                aspect=normalized_aspect,
                sentiment=float(opinion_data.get("sentiment", 0)),
                confidence=float(opinion_data.get("confidence", 0.5)),
                quote=opinion_data.get("quote"),
                summary=opinion_data.get("summary"),
            )
            db.add(opinion)
            created_count += 1

        await db.flush()
        logger.info(f"Created {created_count} opinions for review {review.id}")
        return created_count

    async def _update_product_stats(self, db: AsyncSession, product: Product):
        """Update product review count and average rating."""
        from sqlalchemy import func as sql_func

        # Get review count and average rating
        result = await db.execute(
            select(
                sql_func.count(Review.id).label("count"),
                sql_func.avg(Review.overall_rating).label("avg_rating")
            ).where(Review.product_id == product.id)
        )
        stats = result.one()

        product.review_count = stats.count or 0
        if stats.avg_rating is not None:
            product.average_rating = float(stats.avg_rating)

        logger.info(
            f"Updated product stats: {product.name} - "
            f"{product.review_count} reviews, avg rating: {product.average_rating}"
        )


# Global service instance
_firecrawl_service: Optional[FirecrawlService] = None


def get_firecrawl_service() -> FirecrawlService:
    """Get or create the Firecrawl service singleton."""
    global _firecrawl_service
    if _firecrawl_service is None:
        _firecrawl_service = FirecrawlService()
    return _firecrawl_service
