"""Function registry for Gemini function calling."""

from typing import Dict, Any, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


# Function declarations for Gemini - defines the schema for each function
FUNCTION_DECLARATIONS = [
    {
        "name": "search_products",
        "description": "Search for products by name, category, or keywords. Use this when the user wants to find products or asks about a type of product.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (product name, category, or keywords like 'best phone for gaming')"
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter (smartphones, laptops, headphones, tablets, smartwatches, cameras)",
                    "enum": ["smartphones", "laptops", "headphones", "tablets", "smartwatches", "cameras", "monitors", "keyboards", "mice"]
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 20)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_product_details",
        "description": "Get detailed information about a specific product including specifications and metadata. Use when the user asks about a specific product's features or specs.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "The product ID"
                }
            },
            "required": ["product_id"]
        }
    },
    {
        "name": "get_product_reviews",
        "description": "Get reviews for a product from trusted tech reviewers (YouTube, blogs). Use when the user asks what reviewers think about a product.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "The product ID"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of reviews to return (default 5)"
                }
            },
            "required": ["product_id"]
        }
    },
    {
        "name": "get_review_consensus",
        "description": "Get aggregated consensus from all reviewers about a product. Shows what reviewers agree and disagree on for each aspect (camera, battery, display, etc.). Use when user wants to know the general opinion about a product.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "The product ID"
                }
            },
            "required": ["product_id"]
        }
    },
    {
        "name": "compare_products",
        "description": "Compare multiple products side by side based on reviews and specs. Use when the user asks to compare products or wants to know which is better.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of product IDs to compare (2-5 products)"
                },
                "aspects": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: specific aspects to compare (e.g., battery, camera, performance, display, build_quality)"
                }
            },
            "required": ["product_ids"]
        }
    },
    {
        "name": "scrape_marketplace_listings",
        "description": "Scrape current prices and availability from Amazon and eBay for a product. Use this when user asks where to buy a product and you need fresh marketplace data. This will search marketplaces and store the listings.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name of the product to search for (e.g., 'iPhone 15 Pro', 'Sony WH-1000XM5')"
                },
                "product_id": {
                    "type": "integer",
                    "description": "Optional product ID to associate listings with"
                },
                "marketplaces": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Marketplaces to search (default: ['amazon', 'ebay'])"
                },
                "country": {
                    "type": "string",
                    "description": "Country code (default: US)",
                    "enum": ["US", "UK", "DE", "FR", "JP", "AU", "CA"]
                }
            },
            "required": ["product_name"]
        }
    },
    {
        "name": "find_marketplace_listings",
        "description": "Find where to buy a product with current prices from Amazon, eBay, and other marketplaces. Automatically scrapes fresh listings if none exist or data is stale (>24 hours). Use when the user asks about prices or where to buy.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "The product ID (use this if you have the ID)"
                },
                "product_name": {
                    "type": "string",
                    "description": "Product name to search for (use this if you don't have product_id)"
                },
                "country": {
                    "type": "string",
                    "description": "Country code for marketplace selection (default: US)",
                    "enum": ["US", "UK", "DE", "FR", "JP", "AU", "CA", "ID", "SG", "MY"]
                },
                "force_refresh": {
                    "type": "boolean",
                    "description": "If true, scrape fresh listings even if cached data exists"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_reviewer_info",
        "description": "Get information about a specific tech reviewer including their channel/blog and expertise. Use when user asks about a reviewer.",
        "parameters": {
            "type": "object",
            "properties": {
                "reviewer_id": {
                    "type": "integer",
                    "description": "The reviewer ID"
                }
            },
            "required": ["reviewer_id"]
        }
    },
    {
        "name": "semantic_search",
        "description": "Search across all review content using natural language. Good for specific questions about products that may not be captured by simple keyword search. Use for questions like 'which phone has the best low-light camera?' or 'what do reviewers say about iPhone battery life?'",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results (default 10)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "ingest_youtube_review",
        "description": "Ingest a YouTube video review. Use this when the user provides a YouTube URL and wants to add that review to the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_url": {
                    "type": "string",
                    "description": "URL of the YouTube video to ingest"
                },
                "product_id": {
                    "type": "integer",
                    "description": "Optional product ID if known"
                }
            },
            "required": ["video_url"]
        }
    },
    {
        "name": "ingest_blog_review",
        "description": "Ingest a blog review from a URL. Use this when the user provides a blog URL and wants to add that review to the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the blog review to ingest"
                },
                "product_id": {
                    "type": "integer",
                    "description": "Optional product ID if known"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "gather_product_reviews",
        "description": "Gather and ingest product reviews from YouTube and tech blogs. Use this when the user asks about a product and you need to find reviews. This function searches for reviews, ingests them, and returns aggregated data.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name of the product to gather reviews for (e.g., 'iPhone 15 Pro', 'Samsung Galaxy S24')"
                },
                "force_refresh": {
                    "type": "boolean",
                    "description": "If true, fetch new reviews even if cached data exists (default: false)"
                }
            },
            "required": ["product_name"]
        }
    },
    {
        "name": "search_youtube_reviews",
        "description": "Search for YouTube video reviews of a product. Returns a list of YouTube URLs from trusted tech reviewers. Use this when you specifically need YouTube review URLs.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name of the product to search reviews for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of URLs to return (default: 5)"
                }
            },
            "required": ["product_name"]
        }
    },
    {
        "name": "search_blog_reviews",
        "description": "Search for tech blog reviews of a product. Returns a list of blog URLs from trusted tech publications (The Verge, CNET, TechRadar, etc.). Use this when you specifically need written blog review URLs.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name of the product to search reviews for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of URLs to return (default: 5)"
                }
            },
            "required": ["product_name"]
        }
    }
]


# Registry mapping function names to implementations
_FUNCTION_REGISTRY: Dict[str, Callable[[AsyncSession, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {}


def register_function(name: str):
    """Decorator to register a function implementation."""
    def decorator(func: Callable[[AsyncSession, Dict[str, Any]], Awaitable[Dict[str, Any]]]):
        _FUNCTION_REGISTRY[name] = func
        return func
    return decorator


async def execute_function(
    db: AsyncSession,
    function_name: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute a function by name with given arguments.

    Args:
        db: Database session
        function_name: Name of the function to execute
        args: Arguments to pass to the function

    Returns:
        Function result as a dictionary
    """
    if function_name not in _FUNCTION_REGISTRY:
        logger.error(f"Unknown function: {function_name}")
        return {"error": f"Unknown function: {function_name}"}

    func = _FUNCTION_REGISTRY[function_name]

    try:
        logger.info(f"Executing function: {function_name} with args: {args}")
        result = await func(db, args)
        logger.info(f"Function {function_name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Function {function_name} failed: {e}", exc_info=True)
        return {"error": f"Function execution failed: {str(e)}"}


# Import function implementations to register them
from app.functions import products, reviews, search, comparison, marketplace, reviewers, ingestion, gather

# Ensure all functions are registered
__all__ = ["FUNCTION_DECLARATIONS", "execute_function", "register_function"]
