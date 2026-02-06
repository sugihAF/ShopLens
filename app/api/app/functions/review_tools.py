"""Simplified review tools for the new scraping flow.

This module implements:
1. check_product_cache - Check if product exists in DB with reviews
2. search_youtube_reviews - Find YouTube review URLs via Gemini
3. ingest_youtube_review - Analyze YouTube video and store detailed review
4. search_blog_reviews - Find blog review URLs via Gemini
5. ingest_blog_review - Scrape blog and store detailed review
6. get_reviews_summary - Generate per-reviewer and overall summaries
7. find_marketplace_listings - Real-time marketplace search
"""

import re
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from google import genai
from google.genai import types

from app.functions.registry import register_function
from app.core.config import settings
from app.core.logging import get_logger
from app.models.product import Product
from app.models.reviewer import Reviewer, Platform
from app.models.review import Review, ReviewType, ProcessingStatus

logger = get_logger(__name__)


def _get_gemini_client():
    """Get Gemini client instance."""
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")
    return genai.Client(api_key=settings.GEMINI_API_KEY)


# Default timeout for Gemini API calls (60 seconds)
GEMINI_TIMEOUT = 60


async def _call_gemini_with_timeout(client, model: str, contents, config, timeout: int = GEMINI_TIMEOUT):
    """
    Call Gemini API with a timeout to prevent hanging requests.

    Args:
        client: Gemini client instance
        model: Model name
        contents: Prompt contents
        config: Generation config
        timeout: Timeout in seconds (default 60)

    Returns:
        Gemini API response

    Raises:
        TimeoutError: If the API call times out
    """
    try:
        return await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config
            ),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Gemini API call timed out after {timeout} seconds")
        raise TimeoutError(f"Gemini API call timed out after {timeout} seconds")


# =============================================================================
# Tool 1: Check Product Cache
# =============================================================================

@register_function("check_product_cache")
async def check_product_cache(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if a product exists in the database with reviews.

    Args:
        db: Database session
        args: {product_name: str}

    Returns:
        Dictionary with product info and reviews if found, or not_found status
    """
    product_name = args.get("product_name", "").strip()

    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Checking cache for product: {product_name}")

    # Search for product
    search_term = f"%{product_name}%"
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.reviews).selectinload(Review.reviewer)
        )
        .where(Product.name.ilike(search_term))
        .limit(1)
    )
    product = result.scalar_one_or_none()

    if not product:
        return {
            "status": "not_found",
            "message": f"No cached data for '{product_name}'",
            "product_name": product_name
        }

    # Check if we have reviews
    if not product.reviews:
        return {
            "status": "no_reviews",
            "message": f"Product '{product.name}' found but has no reviews yet",
            "product": {
                "id": product.id,
                "name": product.name,
                "brand": product.brand,
                "category": product.category
            }
        }

    # Format reviews for response
    reviews_data = []
    for review in product.reviews:
        reviews_data.append({
            "id": review.id,
            "title": review.title,
            "content": review.content,
            "summary": review.summary,
            "reviewer_name": review.reviewer.name if review.reviewer else "Unknown",
            "platform": review.reviewer.platform.value if review.reviewer else "unknown",
            "platform_url": review.platform_url,
            "created_at": review.created_at.isoformat() if review.created_at else None
        })

    return {
        "status": "found",
        "product": {
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "review_count": len(reviews_data)
        },
        "reviews": reviews_data
    }


# =============================================================================
# Tool 2: Search YouTube Reviews
# =============================================================================

@register_function("search_youtube_reviews")
async def search_youtube_reviews(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for YouTube review URLs using Gemini with Google Search grounding.

    Args:
        db: Database session
        args: {product_name: str, limit?: int}

    Returns:
        Dictionary with list of YouTube URLs
    """
    product_name = args.get("product_name", "").strip()
    limit = args.get("limit", 3)

    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Searching YouTube reviews for: {product_name}")

    try:
        client = _get_gemini_client()

        prompt = f"""Search for YouTube video reviews of "{product_name}".

Find {limit} high-quality tech review videos from reputable reviewers.

For each video, provide:
1. The exact YouTube URL (must be a real, working URL)
2. The video title
3. The channel name

Return as JSON:
{{
    "videos": [
        {{
            "url": "https://www.youtube.com/watch?v=VIDEO_ID",
            "title": "Video title",
            "channel": "Channel name"
        }}
    ]
}}

Only include real YouTube video URLs that actually exist."""

        response = await _call_gemini_with_timeout(
            client,
            model=settings.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3
            ),
            timeout=60  # 60 second timeout for search
        )

        response_text = response.text or ""

        if not response_text:
            return {
                "status": "no_results",
                "urls": [],
                "product_name": product_name
            }

        # Parse JSON response
        videos = []
        urls = []

        try:
            # Try to extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                videos = data.get("videos", [])
                urls = [v["url"] for v in videos if v.get("url")]
        except json.JSONDecodeError:
            # Fallback: extract URLs with regex
            youtube_pattern = r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+'
            urls = list(set(re.findall(youtube_pattern, response_text)))

        logger.info(f"Found {len(urls)} YouTube URLs for {product_name}")

        return {
            "status": "success",
            "urls": urls[:limit],
            "videos": videos[:limit],
            "product_name": product_name
        }

    except Exception as e:
        logger.error(f"Error searching YouTube reviews: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "urls": [],
            "product_name": product_name
        }


# =============================================================================
# Tool 3: Ingest YouTube Review
# =============================================================================

@register_function("ingest_youtube_review")
async def ingest_youtube_review(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a YouTube video review using Gemini and store the detailed review.

    Args:
        db: Database session
        args: {video_url: str, product_name: str}

    Returns:
        Dictionary with ingestion result
    """
    video_url = args.get("video_url", "").strip()
    product_name = args.get("product_name", "").strip()

    if not video_url:
        return {"error": "video_url is required"}
    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Ingesting YouTube review: {video_url}")

    # Check if already ingested
    existing = await db.execute(
        select(Review).where(Review.platform_url == video_url)
    )
    if existing.scalar_one_or_none():
        return {
            "status": "already_exists",
            "message": f"Review from {video_url} already ingested",
            "url": video_url
        }

    try:
        client = _get_gemini_client()

        # Ask Gemini to analyze the video
        prompt = f"""Analyze this YouTube video review: {video_url}

This is a review of "{product_name}".

Please provide a detailed review analysis including:

1. **Video Information**: Title, channel name, and a brief description of the reviewer's style/credibility.

2. **Detailed Review Content**: Write a comprehensive summary of what the reviewer says about the product. Include:
   - First impressions and unboxing notes (if mentioned)
   - Design and build quality observations
   - Display/screen analysis
   - Performance and speed impressions
   - Camera quality (if applicable)
   - Battery life experience
   - Software and features
   - Any unique insights or testing they performed
   - Comparisons to other products (if mentioned)

3. **Pros and Cons**: List the main advantages and disadvantages mentioned.

4. **Final Verdict**: The reviewer's overall conclusion and recommendation.

Be thorough and detailed. Include specific quotes or observations from the reviewer when possible.
Write at least 3-4 paragraphs for the detailed review content.

Return as JSON:
{{
    "video_title": "Title of the video",
    "channel_name": "Name of the YouTube channel",
    "reviewer_description": "Brief description of the reviewer",
    "detailed_review": "The comprehensive detailed review content (multiple paragraphs)",
    "pros": ["Pro 1", "Pro 2", ...],
    "cons": ["Con 1", "Con 2", ...],
    "verdict": "The reviewer's final verdict",
    "product_name": "Exact product name mentioned",
    "product_brand": "Brand name",
    "product_category": "smartphones/laptops/headphones/etc"
}}"""

        response = await _call_gemini_with_timeout(
            client,
            model=settings.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
                max_output_tokens=4096
            ),
            timeout=120  # 120 second timeout for video analysis
        )

        response_text = response.text or ""

        if not response_text:
            return {
                "status": "error",
                "error": "Empty response from Gemini",
                "url": video_url
            }

        # Parse JSON response
        try:
            # Clean up response
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return {
                "status": "error",
                "error": f"Failed to parse response: {e}",
                "url": video_url
            }

        # Get or create product
        product = await _get_or_create_product(
            db,
            name=data.get("product_name") or product_name,
            brand=data.get("product_brand"),
            category=data.get("product_category", "other")
        )

        # Get or create reviewer
        channel_name = data.get("channel_name", "Unknown Channel")
        reviewer = await _get_or_create_reviewer(
            db,
            name=channel_name,
            platform=Platform.YOUTUBE,
            platform_id=f"youtube:{channel_name.lower().replace(' ', '_')}",
            description=data.get("reviewer_description")
        )

        # Create review with detailed content
        detailed_content = data.get("detailed_review", "")
        pros = data.get("pros", [])
        cons = data.get("cons", [])
        verdict = data.get("verdict", "")

        # Build full content
        full_content = detailed_content
        if pros:
            full_content += f"\n\n**Pros:**\n" + "\n".join(f"- {p}" for p in pros)
        if cons:
            full_content += f"\n\n**Cons:**\n" + "\n".join(f"- {c}" for c in cons)
        if verdict:
            full_content += f"\n\n**Verdict:** {verdict}"

        review = Review(
            product_id=product.id,
            reviewer_id=reviewer.id,
            title=data.get("video_title", "YouTube Review"),
            content=full_content,
            summary=None,  # Will be generated on demand
            platform_url=video_url,
            video_id=_extract_video_id(video_url),
            review_type=ReviewType.FULL_REVIEW,
            review_metadata={
                "pros": pros,
                "cons": cons,
                "verdict": verdict,
                "source": "youtube"
            },
            is_processed=True,
            processing_status=ProcessingStatus.COMPLETED,
            processed_at=datetime.now(timezone.utc)
        )

        db.add(review)
        await db.commit()
        await db.refresh(review)

        logger.info(f"Successfully ingested YouTube review: {video_url}")

        return {
            "status": "success",
            "review_id": review.id,
            "product_id": product.id,
            "reviewer_name": channel_name,
            "title": data.get("video_title"),
            "url": video_url
        }

    except Exception as e:
        logger.error(f"Error ingesting YouTube review: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "url": video_url
        }


# =============================================================================
# Tool 4: Search Blog Reviews
# =============================================================================

@register_function("search_blog_reviews")
async def search_blog_reviews(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for blog review URLs using Gemini with Google Search grounding.

    Args:
        db: Database session
        args: {product_name: str, limit?: int}

    Returns:
        Dictionary with list of blog URLs
    """
    product_name = args.get("product_name", "").strip()
    limit = args.get("limit", 2)

    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Searching blog reviews for: {product_name}")

    try:
        client = _get_gemini_client()

        prompt = f"""Search for written tech blog reviews of "{product_name}".

Find {limit} high-quality written reviews from reputable tech publications like:
- The Verge, CNET, TechRadar, Tom's Guide, Engadget
- GSMArena, Android Authority, 9to5Mac/Google
- Ars Technica, Wired, PCMag

For each review, provide:
1. The exact blog URL (must be a real, working URL)
2. The article title
3. The publication name

Return as JSON:
{{
    "articles": [
        {{
            "url": "https://www.theverge.com/...",
            "title": "Article title",
            "publication": "The Verge"
        }}
    ]
}}

Only include real blog URLs that actually exist."""

        response = await _call_gemini_with_timeout(
            client,
            model=settings.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3
            ),
            timeout=60  # 60 second timeout for search
        )

        response_text = response.text or ""

        if not response_text:
            return {
                "status": "no_results",
                "urls": [],
                "product_name": product_name
            }

        # Parse JSON response
        articles = []
        urls = []

        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                articles = data.get("articles", [])
                urls = [a["url"] for a in articles if a.get("url")]
        except json.JSONDecodeError:
            # Fallback: extract URLs with regex (excluding YouTube)
            url_pattern = r'https?://(?!(?:www\.)?youtube\.com|youtu\.be)[^\s<>"\']+(?:/[^\s<>"\']*)?'
            urls = list(set(re.findall(url_pattern, response_text)))

        logger.info(f"Found {len(urls)} blog URLs for {product_name}")

        return {
            "status": "success",
            "urls": urls[:limit],
            "articles": articles[:limit],
            "product_name": product_name
        }

    except Exception as e:
        logger.error(f"Error searching blog reviews: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "urls": [],
            "product_name": product_name
        }


# =============================================================================
# Tool 5: Ingest Blog Review
# =============================================================================

@register_function("ingest_blog_review")
async def ingest_blog_review(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape a blog review using Firecrawl and extract detailed review using Gemini.

    Args:
        db: Database session
        args: {url: str, product_name: str}

    Returns:
        Dictionary with ingestion result
    """
    url = args.get("url", "").strip()
    product_name = args.get("product_name", "").strip()

    if not url:
        return {"error": "url is required"}
    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Ingesting blog review: {url}")

    # Check if already ingested
    existing = await db.execute(
        select(Review).where(Review.platform_url == url)
    )
    if existing.scalar_one_or_none():
        return {
            "status": "already_exists",
            "message": f"Review from {url} already ingested",
            "url": url
        }

    try:
        # Try to scrape with Firecrawl if available
        content = None

        if settings.FIRECRAWL_API_KEY:
            try:
                from firecrawl import FirecrawlApp
                firecrawl = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
                scrape_result = firecrawl.scrape(url, formats=['markdown'])

                if hasattr(scrape_result, 'markdown'):
                    content = scrape_result.markdown
                elif isinstance(scrape_result, dict):
                    content = scrape_result.get("markdown", "")

            except Exception as e:
                logger.warning(f"Firecrawl failed, falling back to Gemini: {e}")

        client = _get_gemini_client()

        # Use Gemini to analyze (with or without scraped content)
        if content:
            prompt = f"""Analyze this blog review content about "{product_name}":

{content[:30000]}

Please provide a detailed review analysis including:

1. **Publication Info**: Name of the publication and author (if available).

2. **Detailed Review Content**: Write a comprehensive summary of what the reviewer says. Include:
   - Design and build quality observations
   - Display/screen analysis
   - Performance impressions
   - Camera quality (if applicable)
   - Battery life experience
   - Software and features
   - Value for money assessment

3. **Pros and Cons**: List the main advantages and disadvantages mentioned.

4. **Final Verdict**: The reviewer's overall conclusion.

Be thorough and detailed. Write at least 3-4 paragraphs.

Return as JSON:
{{
    "article_title": "Title of the article",
    "publication_name": "Name of the publication",
    "author": "Author name if available",
    "detailed_review": "The comprehensive detailed review content",
    "pros": ["Pro 1", "Pro 2", ...],
    "cons": ["Con 1", "Con 2", ...],
    "verdict": "The reviewer's final verdict",
    "product_name": "Exact product name",
    "product_brand": "Brand name",
    "product_category": "smartphones/laptops/headphones/etc"
}}"""
        else:
            # No Firecrawl content, ask Gemini to find info about the article
            prompt = f"""Analyze this blog review: {url}

This is a review of "{product_name}".

Please provide a detailed review analysis including:

1. **Publication Info**: Name of the publication and author.

2. **Detailed Review Content**: Write a comprehensive summary of what the review says. Include:
   - Design and build quality observations
   - Display/screen analysis
   - Performance impressions
   - Camera quality (if applicable)
   - Battery life experience
   - Software and features
   - Value for money assessment

3. **Pros and Cons**: List the main advantages and disadvantages mentioned.

4. **Final Verdict**: The reviewer's overall conclusion.

Be thorough and detailed. Write at least 3-4 paragraphs.

Return as JSON:
{{
    "article_title": "Title of the article",
    "publication_name": "Name of the publication",
    "author": "Author name if available",
    "detailed_review": "The comprehensive detailed review content",
    "pros": ["Pro 1", "Pro 2", ...],
    "cons": ["Con 1", "Con 2", ...],
    "verdict": "The reviewer's final verdict",
    "product_name": "Exact product name",
    "product_brand": "Brand name",
    "product_category": "smartphones/laptops/headphones/etc"
}}"""

        response = await _call_gemini_with_timeout(
            client,
            model=settings.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())] if not content else None,
                temperature=0.3,
                max_output_tokens=4096
            ),
            timeout=90  # 90 second timeout for blog analysis
        )

        response_text = response.text or ""

        if not response_text:
            return {
                "status": "error",
                "error": "Empty response from Gemini",
                "url": url
            }

        # Parse JSON response
        try:
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return {
                "status": "error",
                "error": f"Failed to parse response: {e}",
                "url": url
            }

        # Get or create product
        product = await _get_or_create_product(
            db,
            name=data.get("product_name") or product_name,
            brand=data.get("product_brand"),
            category=data.get("product_category", "other")
        )

        # Get or create reviewer
        publication_name = data.get("publication_name", "Unknown Blog")
        parsed_url = urlparse(url)
        reviewer = await _get_or_create_reviewer(
            db,
            name=publication_name,
            platform=Platform.BLOG,
            platform_id=f"blog:{parsed_url.netloc}",
            description=f"Tech publication at {parsed_url.netloc}"
        )

        # Create review with detailed content
        detailed_content = data.get("detailed_review", "")
        pros = data.get("pros", [])
        cons = data.get("cons", [])
        verdict = data.get("verdict", "")

        full_content = detailed_content
        if pros:
            full_content += f"\n\n**Pros:**\n" + "\n".join(f"- {p}" for p in pros)
        if cons:
            full_content += f"\n\n**Cons:**\n" + "\n".join(f"- {c}" for c in cons)
        if verdict:
            full_content += f"\n\n**Verdict:** {verdict}"

        review = Review(
            product_id=product.id,
            reviewer_id=reviewer.id,
            title=data.get("article_title", "Blog Review"),
            content=full_content,
            summary=None,
            platform_url=url,
            review_type=ReviewType.FULL_REVIEW,
            review_metadata={
                "pros": pros,
                "cons": cons,
                "verdict": verdict,
                "author": data.get("author"),
                "source": "blog"
            },
            is_processed=True,
            processing_status=ProcessingStatus.COMPLETED,
            processed_at=datetime.now(timezone.utc)
        )

        db.add(review)
        await db.commit()
        await db.refresh(review)

        logger.info(f"Successfully ingested blog review: {url}")

        return {
            "status": "success",
            "review_id": review.id,
            "product_id": product.id,
            "reviewer_name": publication_name,
            "title": data.get("article_title"),
            "url": url
        }

    except Exception as e:
        logger.error(f"Error ingesting blog review: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "url": url
        }


# =============================================================================
# Tool 6: Get Reviews Summary
# =============================================================================

@register_function("get_reviews_summary")
async def get_reviews_summary(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get per-reviewer summaries and overall product summary.

    Args:
        db: Database session
        args: {product_name: str} or {product_id: int}

    Returns:
        Dictionary with reviewer summaries and overall summary
    """
    product_name = args.get("product_name", "").strip()
    product_id = args.get("product_id")

    if not product_name and not product_id:
        return {"error": "product_name or product_id is required"}

    logger.info(f"Getting reviews summary for: {product_name or product_id}")

    # Find product
    if product_id:
        result = await db.execute(
            select(Product)
            .options(selectinload(Product.reviews).selectinload(Review.reviewer))
            .where(Product.id == product_id)
        )
    else:
        result = await db.execute(
            select(Product)
            .options(selectinload(Product.reviews).selectinload(Review.reviewer))
            .where(Product.name.ilike(f"%{product_name}%"))
            .limit(1)
        )

    product = result.scalar_one_or_none()

    if not product:
        return {
            "status": "not_found",
            "message": f"Product not found: {product_name or product_id}"
        }

    if not product.reviews:
        return {
            "status": "no_reviews",
            "message": f"No reviews found for {product.name}",
            "product": {
                "id": product.id,
                "name": product.name
            }
        }

    try:
        client = _get_gemini_client()

        # Build context from all reviews
        reviews_context = []
        for review in product.reviews:
            reviewer_name = review.reviewer.name if review.reviewer else "Unknown"
            platform = review.reviewer.platform.value if review.reviewer else "unknown"
            reviews_context.append(f"""
### {reviewer_name} ({platform})
URL: {review.platform_url}

{review.content}
""")

        all_reviews_text = "\n---\n".join(reviews_context)

        # Ask Gemini to generate summaries
        prompt = f"""Based on the following reviews of "{product.name}", provide:

1. **Per-Reviewer Summaries**: For each reviewer, write a detailed paragraph (at least 4-5 sentences) summarizing their key opinions, what they liked, what they didn't like, and their overall impression.

2. **Overall Summary**: Write a comprehensive summary (2-3 paragraphs) that synthesizes all the reviews, highlighting:
   - Common praise points across reviewers
   - Common criticisms
   - Key differentiating opinions
   - Overall consensus on whether the product is recommended

Reviews:
{all_reviews_text}

Return as JSON:
{{
    "reviewer_summaries": [
        {{
            "reviewer_name": "Name",
            "platform": "youtube/blog",
            "url": "Review URL",
            "summary": "Detailed paragraph summary of their review..."
        }}
    ],
    "overall_summary": "Comprehensive overall summary paragraphs...",
    "common_pros": ["Common positive point 1", "Common positive point 2"],
    "common_cons": ["Common criticism 1", "Common criticism 2"]
}}"""

        response = await _call_gemini_with_timeout(
            client,
            model=settings.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=4096
            ),
            timeout=90  # 90 second timeout for summary generation
        )

        response_text = response.text or ""

        # Parse response
        try:
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found")

        except (json.JSONDecodeError, ValueError):
            # Fallback: return raw text
            return {
                "status": "success",
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "brand": product.brand
                },
                "reviewer_summaries": [
                    {
                        "reviewer_name": r.reviewer.name if r.reviewer else "Unknown",
                        "platform": r.reviewer.platform.value if r.reviewer else "unknown",
                        "url": r.platform_url,
                        "summary": r.content[:500] + "..." if len(r.content) > 500 else r.content
                    }
                    for r in product.reviews
                ],
                "overall_summary": response_text,
                "total_reviews": len(product.reviews)
            }

        return {
            "status": "success",
            "product": {
                "id": product.id,
                "name": product.name,
                "brand": product.brand,
                "category": product.category
            },
            "reviewer_summaries": data.get("reviewer_summaries", []),
            "overall_summary": data.get("overall_summary", ""),
            "common_pros": data.get("common_pros", []),
            "common_cons": data.get("common_cons", []),
            "total_reviews": len(product.reviews)
        }

    except Exception as e:
        logger.error(f"Error generating summaries: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


# =============================================================================
# Tool 7: Find Marketplace Listings (Real-time)
# =============================================================================

@register_function("find_marketplace_listings")
async def find_marketplace_listings(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for product listings on Amazon and eBay in real-time.

    Args:
        db: Database session
        args: {product_name: str, count_per_marketplace?: int}

    Returns:
        Dictionary with marketplace listings
    """
    product_name = args.get("product_name", "").strip()
    count_per_marketplace = args.get("count_per_marketplace", 2)

    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Searching marketplace listings for: {product_name}")

    try:
        client = _get_gemini_client()

        prompt = f"""Search for where to buy "{product_name}" online.

Find {count_per_marketplace} listings each from:
1. Amazon (amazon.com)
2. eBay (ebay.com)

For each listing, provide:
- The exact product URL
- The product title
- The price (if available)
- The seller/condition info

Return as JSON:
{{
    "amazon": [
        {{
            "url": "https://www.amazon.com/...",
            "title": "Product title",
            "price": "$XXX.XX",
            "seller": "Seller info"
        }}
    ],
    "ebay": [
        {{
            "url": "https://www.ebay.com/...",
            "title": "Product title",
            "price": "$XXX.XX",
            "condition": "New/Used"
        }}
    ]
}}

Only include real, working URLs."""

        response = await _call_gemini_with_timeout(
            client,
            model=settings.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3
            ),
            timeout=60  # 60 second timeout for marketplace search
        )

        response_text = response.text or ""

        if not response_text:
            return {
                "status": "no_results",
                "message": "Could not find marketplace listings",
                "product_name": product_name
            }

        # Parse response
        try:
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found")

        except (json.JSONDecodeError, ValueError):
            # Fallback: extract URLs
            amazon_urls = re.findall(r'https?://(?:www\.)?amazon\.com[^\s<>"\']+', response_text)
            ebay_urls = re.findall(r'https?://(?:www\.)?ebay\.com[^\s<>"\']+', response_text)

            return {
                "status": "partial",
                "amazon": [{"url": u} for u in amazon_urls[:count_per_marketplace]],
                "ebay": [{"url": u} for u in ebay_urls[:count_per_marketplace]],
                "product_name": product_name
            }

        return {
            "status": "success",
            "amazon": data.get("amazon", [])[:count_per_marketplace],
            "ebay": data.get("ebay", [])[:count_per_marketplace],
            "product_name": product_name
        }

    except Exception as e:
        logger.error(f"Error finding marketplace listings: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "product_name": product_name
        }


# =============================================================================
# Helper Functions
# =============================================================================

async def _get_or_create_product(
    db: AsyncSession,
    name: str,
    brand: Optional[str] = None,
    category: str = "other"
) -> Product:
    """Get existing product or create a new one."""
    # Try to find existing product
    result = await db.execute(
        select(Product).where(Product.name.ilike(f"%{name}%")).limit(1)
    )
    product = result.scalar_one_or_none()

    if product:
        return product

    # Create new product
    product = Product(
        name=name,
        brand=brand,
        category=category.lower() if category else "other"
    )
    db.add(product)
    await db.flush()

    logger.info(f"Created new product: {name} (ID: {product.id})")
    return product


async def _get_or_create_reviewer(
    db: AsyncSession,
    name: str,
    platform: Platform,
    platform_id: str,
    description: Optional[str] = None
) -> Reviewer:
    """Get existing reviewer or create a new one."""
    result = await db.execute(
        select(Reviewer).where(Reviewer.platform_id == platform_id)
    )
    reviewer = result.scalar_one_or_none()

    if reviewer:
        return reviewer

    reviewer = Reviewer(
        name=name,
        platform=platform,
        platform_id=platform_id,
        description=description,
        credibility_score=0.5,
        is_active=True,
        is_verified=False
    )
    db.add(reviewer)
    await db.flush()

    logger.info(f"Created new reviewer: {name} (ID: {reviewer.id})")
    return reviewer


def _extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
