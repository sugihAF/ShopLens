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
import httpx
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
from app.core.logging import get_logger, log_success, log_detail, log_fail, log_warn
from app.models.product import Product
from app.models.reviewer import Reviewer, Platform
from app.models.review import Review, ReviewType, ProcessingStatus

logger = get_logger(__name__)

# Firecrawl search API
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"


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


async def _call_gemini_with_retry(client, model: str, contents, config, timeout: int = GEMINI_TIMEOUT, max_retries: int = 1):
    """
    Call Gemini API with timeout and retry on failure.

    Args:
        client: Gemini client instance
        model: Model name
        contents: Prompt contents
        config: Generation config
        timeout: Timeout in seconds per attempt
        max_retries: Number of retries after first failure (default 1, so 2 total attempts)

    Returns:
        Gemini API response
    """
    last_error = None
    for attempt in range(1 + max_retries):
        try:
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{max_retries}...")
            return await _call_gemini_with_timeout(client, model, contents, config, timeout)
        except (TimeoutError, Exception) as e:
            last_error = e
            logger.warning(f"Gemini call failed (attempt {attempt + 1}/{1 + max_retries}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(2)  # Brief pause before retry
    raise last_error


def _extract_urls_from_grounding(response, domain_filter: Optional[str] = None) -> List[str]:
    """
    Extract URLs from Gemini grounding metadata chunks.

    The grounding_metadata.grounding_chunks contain the actual URLs that
    Google Search found — these are real, verified URLs.

    Args:
        response: Gemini API response object
        domain_filter: Optional domain substring to filter (e.g. "youtube.com")

    Returns:
        Deduplicated list of URLs from grounding chunks
    """
    urls = []
    try:
        metadata = response.candidates[0].grounding_metadata
        if not metadata or not metadata.grounding_chunks:
            logger.debug("No grounding_metadata or grounding_chunks in response")
            return urls
        for chunk in metadata.grounding_chunks:
            if hasattr(chunk, 'web') and chunk.web and hasattr(chunk.web, 'uri'):
                uri = chunk.web.uri
                if uri and (domain_filter is None or domain_filter in uri):
                    urls.append(uri)
        logger.debug(f"Grounding chunks: {len(metadata.grounding_chunks)} total, "
                     f"{len(urls)} matched filter '{domain_filter}'")
    except (AttributeError, IndexError) as e:
        logger.debug(f"Could not extract grounding URLs: {e}")
    # Deduplicate while preserving order
    seen = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def _log_all_grounding_urls(response) -> List[str]:
    """Log all URLs from grounding metadata for debugging."""
    all_urls = _extract_urls_from_grounding(response, domain_filter=None)
    if all_urls:
        logger.debug(f"All grounding URLs ({len(all_urls)}): {all_urls}")
    else:
        logger.debug("No grounding URLs found in response")
    return all_urls


def _is_youtube_video_url(url: str) -> bool:
    """Check if a URL is a YouTube video URL (not a channel, playlist, or homepage)."""
    return bool(re.match(
        r'https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]{11}|youtu\.be/[\w-]{11})',
        url
    ))


async def _firecrawl_search(query: str, limit: int = 5, timeout: int = 30) -> List[Dict[str, Any]]:
    """
    Search the web using Firecrawl search API.

    Args:
        query: Search query string
        limit: Max number of results
        timeout: Request timeout in seconds

    Returns:
        List of search result dicts with 'url', 'title', 'description' keys.
        Returns empty list on failure.
    """
    if not settings.FIRECRAWL_API_KEY:
        logger.warning("FIRECRAWL_API_KEY not set — cannot use Firecrawl search")
        return []

    payload = {
        "query": query,
        "limit": limit,
        "scrapeOptions": {
            "onlyMainContent": False,
            "formats": []
        }
    }
    headers = {
        "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(FIRECRAWL_SEARCH_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Firecrawl v2 returns data in two possible formats:
        # Format A: {"data": [{"url": ..., "title": ...}, ...]}  — flat array
        # Format B: {"data": {"web": [...], "news": [...], ...}}  — nested by source
        raw_data = data.get("data", []) if isinstance(data, dict) else data

        # Normalize to a flat list of result dicts
        results = []
        if isinstance(raw_data, list):
            results = raw_data
        elif isinstance(raw_data, dict):
            for source_key in ("web", "news"):
                items = raw_data.get(source_key, [])
                if isinstance(items, list):
                    results.extend(items)

        logger.debug(f"Firecrawl: {len(results)} results for: {query}")
        return results

    except httpx.TimeoutException:
        logger.error(f"Firecrawl search timed out after {timeout}s for: {query}")
        return []
    except Exception as e:
        logger.error(f"Firecrawl search failed: {e}")
        return []


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

    logger.debug(f"Cache lookup: {product_name}")

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
    Search for YouTube review URLs using Firecrawl search API.

    Uses Firecrawl to perform a real web search, returning verified URLs.
    Filters results to only include actual YouTube video URLs.

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

    logger.debug(f"YouTube search: {product_name}")

    try:
        query = f"{product_name} review youtube video site:youtube.com"
        results = await _firecrawl_search(query, limit=limit * 3, timeout=30)

        logger.debug(f"Firecrawl raw URLs: {[r.get('url', '?') for r in results]}")

        # Filter to actual YouTube video URLs
        video_urls = []
        videos = []
        seen = set()

        for r in results:
            url = r.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)

            if _is_youtube_video_url(url):
                video_urls.append(url)
                videos.append({
                    "url": url,
                    "title": r.get("title", ""),
                    "description": r.get("description", "")
                })

            if len(video_urls) >= limit:
                break

        log_detail(logger, f"Firecrawl {len(results)} raw → {len(video_urls)} YouTube URLs")

        return {
            "status": "success" if video_urls else "no_results",
            "urls": video_urls[:limit],
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

    # Validate URL is a real YouTube video URL
    if not _is_youtube_video_url(video_url):
        return {
            "status": "error",
            "error": f"Invalid YouTube video URL: {video_url}",
            "url": video_url
        }

    logger.debug(f"YouTube ingest: {video_url}")

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

        # Ask Gemini to analyze the video — emphasis on THIS SPECIFIC video
        prompt = f"""Go to this exact YouTube video URL and analyze it: {video_url}

I need a detailed review analysis of THIS SPECIFIC VIDEO. Do not confuse it with other videos.
The video should be a review of or related to "{product_name}".

Please provide:

1. **Video Information**: The exact title of THIS video, the channel name, and a brief description of the reviewer.

2. **Detailed Review Content**: Write a comprehensive summary of what the reviewer says in THIS video. Include:
   - First impressions and unboxing notes (if mentioned)
   - Design and build quality observations
   - Display/screen analysis
   - Performance and speed impressions
   - Camera quality (if applicable)
   - Battery life experience
   - Software and features
   - Any unique insights or testing they performed
   - Comparisons to other products (if mentioned)

3. **Pros and Cons**: List the main advantages and disadvantages mentioned in THIS video.

4. **Final Verdict**: The reviewer's overall conclusion and recommendation.

Be thorough and detailed. Include specific quotes or observations from the reviewer when possible.
Write at least 3-4 paragraphs for the detailed review content.

IMPORTANT: Only report what is actually said in THIS video at {video_url}. Do not mix in content from other videos.

Return as JSON:
{{
    "video_title": "Exact title of this video",
    "channel_name": "Name of the YouTube channel",
    "reviewer_description": "Brief description of the reviewer",
    "detailed_review": "The comprehensive detailed review content (multiple paragraphs)",
    "pros": ["Pro 1", "Pro 2", ...],
    "cons": ["Con 1", "Con 2", ...],
    "verdict": "The reviewer's final verdict",
    "product_name": "Exact product name reviewed in this video",
    "product_brand": "Brand name",
    "product_category": "smartphones/laptops/headphones/etc"
}}"""

        response = await _call_gemini_with_retry(
            client,
            model=settings.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
                max_output_tokens=4096
            ),
            timeout=120,  # 120 second timeout for video analysis
            max_retries=1
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

        log_detail(logger, f"Ingested: \"{data.get('video_title', '?')}\" by {channel_name}")

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
    Search for blog review URLs using Firecrawl search API.

    Uses Firecrawl to perform a real web search, returning verified URLs.
    Filters results to exclude YouTube and only include blog/article URLs.

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

    logger.debug(f"Blog search: {product_name}")

    try:
        query = f"{product_name} review from The Verge OR CNET OR TechRadar OR Tom's Guide OR Engadget OR GSMArena OR Android Authority OR Ars Technica OR Wired OR PCMag"
        results = await _firecrawl_search(query, limit=limit * 3, timeout=30)

        # Filter out YouTube URLs — we only want blog/article URLs
        blog_urls = []
        articles = []
        seen = set()

        for r in results:
            url = r.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)

            if "youtube.com" in url or "youtu.be" in url:
                continue

            blog_urls.append(url)
            articles.append({
                "url": url,
                "title": r.get("title", ""),
                "description": r.get("description", "")
            })

            if len(blog_urls) >= limit:
                break

        log_detail(logger, f"Firecrawl {len(results)} raw → {len(blog_urls)} blog URLs")

        return {
            "status": "success" if blog_urls else "no_results",
            "urls": blog_urls[:limit],
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

    logger.debug(f"Blog ingest: {url}")

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
                log_warn(logger, f"Firecrawl scrape failed, falling back to Gemini: {e}")

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

        response = await _call_gemini_with_retry(
            client,
            model=settings.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())] if not content else None,
                temperature=0.3,
                max_output_tokens=4096
            ),
            timeout=90,  # 90 second timeout for blog analysis
            max_retries=1
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

        log_detail(logger, f"Ingested: \"{data.get('article_title', '?')}\" from {publication_name}")

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

    logger.debug(f"Summary generation: {product_name or product_id}")

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
    Search for product listings on Amazon and eBay using Firecrawl search API.

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

    logger.debug(f"Marketplace search: {product_name}")

    try:
        # Search Amazon and eBay concurrently via Firecrawl
        amazon_query = f"{product_name} site:amazon.com"
        ebay_query = f"{product_name} site:ebay.com"

        amazon_results, ebay_results = await asyncio.gather(
            _firecrawl_search(amazon_query, limit=count_per_marketplace * 2, timeout=30),
            _firecrawl_search(ebay_query, limit=count_per_marketplace * 2, timeout=30),
        )

        # Filter and format Amazon results
        amazon_listings = []
        for r in amazon_results:
            url = r.get("url", "")
            if "amazon.com" not in url:
                continue
            amazon_listings.append({
                "url": url,
                "title": r.get("title", ""),
                "price": "",
                "seller": r.get("description", "")[:120] if r.get("description") else "",
            })
            if len(amazon_listings) >= count_per_marketplace:
                break

        # Filter and format eBay results
        ebay_listings = []
        for r in ebay_results:
            url = r.get("url", "")
            if "ebay.com" not in url:
                continue
            ebay_listings.append({
                "url": url,
                "title": r.get("title", ""),
                "price": "",
                "condition": r.get("description", "")[:120] if r.get("description") else "",
            })
            if len(ebay_listings) >= count_per_marketplace:
                break

        if not amazon_listings and not ebay_listings:
            return {
                "status": "no_results",
                "message": "Could not find marketplace listings",
                "product_name": product_name,
            }

        status = "success" if amazon_listings and ebay_listings else "partial"
        logger.info(f"Marketplace: {len(amazon_listings)} Amazon + {len(ebay_listings)} eBay listings for {product_name}")

        return {
            "status": status,
            "amazon": amazon_listings,
            "ebay": ebay_listings,
            "product_name": product_name,
        }

    except Exception as e:
        logger.error(f"Error finding marketplace listings: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "product_name": product_name,
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

    log_detail(logger, f"DB: new product \"{name}\" (id={product.id})")
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

    log_detail(logger, f"DB: new reviewer \"{name}\" (id={reviewer.id})")
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
