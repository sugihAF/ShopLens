"""Function registry for Gemini function calling."""

from typing import Dict, Any, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


# Function declarations for Gemini - defines the schema for each function
# Primary review flow tools (NEW - simplified flow)
FUNCTION_DECLARATIONS = [
    # =========================================================================
    # PRIMARY REVIEW FLOW TOOLS (Use these for the main review workflow)
    # =========================================================================
    {
        "name": "check_product_cache",
        "description": "Check if a product exists in the database with cached reviews. Use this FIRST when user asks about a product to check if we already have review data.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name of the product to search for (e.g., 'Samsung Galaxy S25', 'iPhone 15 Pro')"
                }
            },
            "required": ["product_name"]
        }
    },
    {
        "name": "search_youtube_reviews",
        "description": "Search for YouTube video review URLs for a product. Returns a list of YouTube URLs. Use this after check_product_cache returns no results.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name of the product to search reviews for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of YouTube URLs to return (default: 3)"
                }
            },
            "required": ["product_name"]
        }
    },
    {
        "name": "ingest_youtube_review",
        "description": "Analyze a YouTube video review using AI and store the detailed review in the database. Call this for EACH YouTube URL returned by search_youtube_reviews.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_url": {
                    "type": "string",
                    "description": "URL of the YouTube video to analyze and ingest"
                },
                "product_name": {
                    "type": "string",
                    "description": "Name of the product being reviewed"
                }
            },
            "required": ["video_url", "product_name"]
        }
    },
    {
        "name": "search_blog_reviews",
        "description": "Search for blog review URLs for a product from tech publications. Returns a list of blog URLs. Use this to find written reviews.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name of the product to search reviews for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of blog URLs to return (default: 2)"
                }
            },
            "required": ["product_name"]
        }
    },
    {
        "name": "ingest_blog_review",
        "description": "Scrape and analyze a blog review, then store the detailed review in the database. Call this for EACH blog URL returned by search_blog_reviews.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the blog review to scrape and ingest"
                },
                "product_name": {
                    "type": "string",
                    "description": "Name of the product being reviewed"
                }
            },
            "required": ["url", "product_name"]
        }
    },
    {
        "name": "get_reviews_summary",
        "description": "Generate per-reviewer summaries and an overall product summary from stored reviews. Use this AFTER reviews have been ingested to present the final summary to the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name of the product to summarize reviews for"
                },
                "product_id": {
                    "type": "integer",
                    "description": "Product ID if known (alternative to product_name)"
                }
            },
            "required": []
        }
    },
    {
        "name": "find_marketplace_listings",
        "description": "Search for where to buy a product on Amazon and eBay. Returns real-time listings with prices and links. Use when user asks 'where can I buy this' or about prices.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Name of the product to search for"
                },
                "count_per_marketplace": {
                    "type": "integer",
                    "description": "Number of listings to return per marketplace (default: 2)"
                }
            },
            "required": ["product_name"]
        }
    },
    # =========================================================================
    # SECONDARY/LEGACY TOOLS (for additional functionality)
    # =========================================================================
    {
        "name": "search_products",
        "description": "Search for products in the database by name, category, or keywords.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (product name, category, or keywords)"
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
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
        "description": "Get detailed information about a specific product including specifications.",
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
        "description": "Get raw reviews for a product from the database.",
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
        "name": "compare_products",
        "description": "Compare multiple products side by side based on reviews.",
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
                    "description": "Specific aspects to compare (e.g., battery, camera, performance)"
                }
            },
            "required": ["product_ids"]
        }
    },
    {
        "name": "get_reviewer_info",
        "description": "Get information about a specific tech reviewer.",
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
# Import new simplified review tools
from app.functions import review_tools

# Ensure all functions are registered
__all__ = ["FUNCTION_DECLARATIONS", "execute_function", "register_function"]
