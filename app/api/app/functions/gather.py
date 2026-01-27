"""Gather functions for auto-scraping product reviews from YouTube and blogs."""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from google import genai
from google.genai import types

from app.functions.registry import register_function
from app.core.config import settings
from app.core.logging import get_logger
from app.crud.product import product_crud
from app.crud.review import review_crud
from app.models.product import Product
from app.models.review import Review
from app.services.youtube_scraper import youtube_scraper
from app.services.firecrawl_service import get_firecrawl_service

logger = get_logger(__name__)

# Cache TTL for reviews (7 days in hours)
REVIEW_CACHE_TTL_HOURS = 168


def _is_data_fresh(updated_at: Optional[datetime], ttl_hours: int = REVIEW_CACHE_TTL_HOURS) -> bool:
    """Check if data is still fresh based on TTL."""
    if not updated_at:
        return False
    now = datetime.now(timezone.utc)
    # Handle timezone-naive datetime
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age = now - updated_at
    return age < timedelta(hours=ttl_hours)


@register_function("gather_product_reviews")
async def gather_product_reviews(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gather product reviews by searching YouTube and blogs, then ingesting top results.

    This is the main function for getting review data about a product. It:
    1. Checks if product already exists in DB with recent reviews
    2. If not, searches for YouTube and blog reviews
    3. Ingests top results from each source
    4. Returns aggregated review data

    Args:
        db: Database session
        args: {product_name: str, force_refresh?: bool}

    Returns:
        Dictionary with product info, reviews, and sources
    """
    product_name = args.get("product_name")
    force_refresh = args.get("force_refresh", False)

    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Gathering reviews for: {product_name} (force_refresh={force_refresh})")

    # Step 1: Check if product exists with recent reviews
    products = await product_crud.search(db, query=product_name, limit=1)
    product = products[0] if products else None

    if product and not force_refresh:
        # Check if we have recent reviews
        reviews = await review_crud.get_by_product(db, product_id=product.id, limit=10)

        if reviews and _is_data_fresh(product.updated_at):
            logger.info(f"Using cached reviews for product: {product.name}")
            return _format_product_reviews(product, reviews)

    # Step 2: Search for new reviews
    youtube_urls = []
    blog_urls = []

    try:
        # Search YouTube and blogs in parallel
        youtube_result, blog_result = await asyncio.gather(
            search_youtube_reviews(db, {"product_name": product_name, "limit": 3}),
            search_blog_reviews(db, {"product_name": product_name, "limit": 3}),
            return_exceptions=True
        )

        if not isinstance(youtube_result, Exception) and youtube_result.get("urls"):
            youtube_urls = youtube_result["urls"]
        else:
            logger.warning(f"YouTube search failed or returned no results: {youtube_result}")

        if not isinstance(blog_result, Exception) and blog_result.get("urls"):
            blog_urls = blog_result["urls"]
        else:
            logger.warning(f"Blog search failed or returned no results: {blog_result}")

    except Exception as e:
        logger.error(f"Error searching for reviews: {e}", exc_info=True)

    if not youtube_urls and not blog_urls:
        # If we have existing data, return it even if not fresh
        if product:
            reviews = await review_crud.get_by_product(db, product_id=product.id, limit=10)
            if reviews:
                return _format_product_reviews(product, reviews)

        return {
            "status": "no_results",
            "message": f"Could not find reviews for '{product_name}'. Try a more specific product name.",
            "product_name": product_name,
            "reviews": [],
            "sources": []
        }

    # Step 3: Ingest reviews
    ingested_reviews = []
    sources = []

    # Ingest YouTube reviews
    for url in youtube_urls[:3]:  # Limit to 3 per source
        try:
            result = await youtube_scraper.ingest_youtube_review(
                db=db,
                video_url=url,
                product_id=product.id if product else None
            )
            if result.get("status") in ["success", "exists"]:
                ingested_reviews.append(result)
                sources.append({
                    "type": "youtube",
                    "url": url,
                    "status": result.get("status")
                })
        except Exception as e:
            logger.error(f"Failed to ingest YouTube review {url}: {e}")
            sources.append({
                "type": "youtube",
                "url": url,
                "status": "error",
                "error": str(e)
            })

    # Ingest blog reviews
    firecrawl_service = get_firecrawl_service()
    for url in blog_urls[:3]:  # Limit to 3 per source
        try:
            result = await firecrawl_service.ingest_blog_review(
                db=db,
                url=url,
                product_id=product.id if product else None
            )
            if result.get("status") in ["success", "already_exists"]:
                ingested_reviews.append(result)
                sources.append({
                    "type": "blog",
                    "url": url,
                    "status": result.get("status")
                })
        except Exception as e:
            logger.error(f"Failed to ingest blog review {url}: {e}")
            sources.append({
                "type": "blog",
                "url": url,
                "status": "error",
                "error": str(e)
            })

    # Commit changes
    await db.commit()

    # Step 4: Get updated product and reviews
    if not product and ingested_reviews:
        # Try to find the product that was created
        product_id = ingested_reviews[0].get("product_id")
        if product_id:
            product = await product_crud.get(db, id=product_id)

    if product:
        reviews = await review_crud.get_by_product(db, product_id=product.id, limit=10)
        return _format_product_reviews(product, reviews, sources)

    return {
        "status": "partial",
        "message": f"Ingested {len(ingested_reviews)} reviews but could not find product",
        "product_name": product_name,
        "reviews_ingested": len(ingested_reviews),
        "sources": sources
    }


def _format_product_reviews(
    product: Product,
    reviews: List[Review],
    sources: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """Format product and reviews for response."""
    formatted_reviews = []
    reviewer_names = set()

    for review in reviews:
        reviewer_name = review.reviewer.name if review.reviewer else "Unknown"
        reviewer_names.add(reviewer_name)

        formatted_reviews.append({
            "id": review.id,
            "title": review.title,
            "summary": review.summary,
            "overall_rating": review.overall_rating,
            "reviewer": reviewer_name,
            "reviewer_id": review.reviewer_id,
            "platform_url": review.platform_url,
            "review_type": review.review_type.value if review.review_type else None,
            "pros": review.review_metadata.get("pros", []) if review.review_metadata else [],
            "cons": review.review_metadata.get("cons", []) if review.review_metadata else [],
            "published_at": review.published_at.isoformat() if review.published_at else None
        })

    return {
        "status": "success",
        "product": {
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "review_count": product.review_count,
            "average_rating": float(product.average_rating) if product.average_rating else None
        },
        "reviews": formatted_reviews,
        "sources": list(reviewer_names),
        "total_reviews": len(formatted_reviews),
        "sources_detail": sources
    }


@register_function("search_youtube_reviews")
async def search_youtube_reviews(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for YouTube review URLs for a product using Gemini with Google Search grounding.

    Args:
        db: Database session (not used but required by registry)
        args: {product_name: str, limit?: int}

    Returns:
        Dictionary with list of YouTube URLs
    """
    product_name = args.get("product_name")
    limit = args.get("limit", 5)

    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Searching YouTube reviews for: {product_name}")

    # Initialize Gemini client
    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured"}

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Search prompt focusing on tech reviewers
    search_prompt = f"""Search for YouTube video reviews of "{product_name}".

I need you to find {limit} high-quality tech review videos for this product.

Prioritize videos from well-known tech reviewers such as:
- MKBHD (Marques Brownlee)
- Linus Tech Tips
- Dave2D
- Unbox Therapy
- JerryRigEverything
- The Verge
- Tom's Guide
- iJustine
- Austin Evans
- MrMobile

For each video found, provide the full YouTube URL.

Return your response as a JSON object with this structure:
{{
    "urls": [
        "https://www.youtube.com/watch?v=VIDEO_ID_1",
        "https://www.youtube.com/watch?v=VIDEO_ID_2"
    ],
    "videos": [
        {{
            "url": "https://www.youtube.com/watch?v=VIDEO_ID_1",
            "title": "Video title",
            "channel": "Channel name"
        }}
    ]
}}

Only include actual YouTube video URLs that exist. Do not make up URLs."""

    try:
        response = await client.aio.models.generate_content(
            model=settings.LLM_MODEL,
            contents=search_prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3
            )
        )

        response_text = response.text

        # Extract URLs from response
        import re
        import json

        # Try to parse as JSON first
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                urls = data.get("urls", [])
                if urls:
                    logger.info(f"Found {len(urls)} YouTube URLs for {product_name}")
                    return {
                        "status": "success",
                        "urls": urls[:limit],
                        "videos": data.get("videos", [])[:limit],
                        "product_name": product_name
                    }
        except json.JSONDecodeError:
            pass

        # Fallback: extract URLs using regex
        youtube_pattern = r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+'
        urls = re.findall(youtube_pattern, response_text)
        urls = list(dict.fromkeys(urls))  # Remove duplicates while preserving order

        if urls:
            logger.info(f"Extracted {len(urls)} YouTube URLs for {product_name}")
            return {
                "status": "success",
                "urls": urls[:limit],
                "product_name": product_name
            }

        return {
            "status": "no_results",
            "message": f"No YouTube reviews found for '{product_name}'",
            "urls": [],
            "product_name": product_name
        }

    except Exception as e:
        logger.error(f"Error searching YouTube reviews: {e}", exc_info=True)
        return {
            "error": f"Search failed: {str(e)}",
            "urls": [],
            "product_name": product_name
        }


@register_function("search_blog_reviews")
async def search_blog_reviews(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for tech blog review URLs for a product using Gemini with Google Search grounding.

    Args:
        db: Database session (not used but required by registry)
        args: {product_name: str, limit?: int}

    Returns:
        Dictionary with list of blog URLs
    """
    product_name = args.get("product_name")
    limit = args.get("limit", 5)

    if not product_name:
        return {"error": "product_name is required"}

    logger.info(f"Searching blog reviews for: {product_name}")

    # Initialize Gemini client
    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured"}

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Search prompt focusing on tech blogs
    search_prompt = f"""Search for written tech blog reviews of "{product_name}".

I need you to find {limit} high-quality written reviews from reputable tech publications.

Prioritize reviews from well-known tech publications such as:
- The Verge
- TechCrunch
- Ars Technica
- Tom's Guide
- CNET
- TechRadar
- Wired
- Engadget
- Android Authority
- 9to5Mac / 9to5Google
- GSMArena (for phones)
- NotebookCheck (for laptops)

For each review found, provide the full URL.

Return your response as a JSON object with this structure:
{{
    "urls": [
        "https://www.theverge.com/review/...",
        "https://www.cnet.com/reviews/..."
    ],
    "articles": [
        {{
            "url": "https://www.theverge.com/review/...",
            "title": "Article title",
            "publication": "The Verge"
        }}
    ]
}}

Only include actual blog review URLs that exist. Do not make up URLs."""

    try:
        response = await client.aio.models.generate_content(
            model=settings.LLM_MODEL,
            contents=search_prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3
            )
        )

        response_text = response.text

        # Extract URLs from response
        import re
        import json

        # Try to parse as JSON first
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                urls = data.get("urls", [])
                if urls:
                    logger.info(f"Found {len(urls)} blog URLs for {product_name}")
                    return {
                        "status": "success",
                        "urls": urls[:limit],
                        "articles": data.get("articles", [])[:limit],
                        "product_name": product_name
                    }
        except json.JSONDecodeError:
            pass

        # Fallback: extract URLs using regex (excluding YouTube)
        url_pattern = r'https?://(?!(?:www\.)?youtube\.com|youtu\.be)[^\s<>"\']+(?:/[^\s<>"\']*)?'
        urls = re.findall(url_pattern, response_text)

        # Filter to likely review URLs
        review_domains = [
            'theverge.com', 'techcrunch.com', 'arstechnica.com', 'tomsguide.com',
            'cnet.com', 'techradar.com', 'wired.com', 'engadget.com',
            'androidauthority.com', '9to5mac.com', '9to5google.com',
            'gsmarena.com', 'notebookcheck.net', 'anandtech.com',
            'pcmag.com', 'digitaltrends.com'
        ]

        filtered_urls = []
        for url in urls:
            for domain in review_domains:
                if domain in url.lower():
                    filtered_urls.append(url)
                    break

        # Remove duplicates while preserving order
        filtered_urls = list(dict.fromkeys(filtered_urls))

        if filtered_urls:
            logger.info(f"Extracted {len(filtered_urls)} blog URLs for {product_name}")
            return {
                "status": "success",
                "urls": filtered_urls[:limit],
                "product_name": product_name
            }

        return {
            "status": "no_results",
            "message": f"No blog reviews found for '{product_name}'",
            "urls": [],
            "product_name": product_name
        }

    except Exception as e:
        logger.error(f"Error searching blog reviews: {e}", exc_info=True)
        return {
            "error": f"Search failed: {str(e)}",
            "urls": [],
            "product_name": product_name
        }
