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
        "name": "find_marketplace_listings",
        "description": "Find where to buy a product with current prices from various marketplaces. Use when the user asks about prices or where to buy.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "The product ID"
                },
                "country": {
                    "type": "string",
                    "description": "Country code for marketplace selection (default: ID for Indonesia)",
                    "enum": ["ID", "US", "UK", "SG", "MY", "AU"]
                }
            },
            "required": ["product_id"]
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
from app.functions import products, reviews, search, comparison, marketplace, reviewers, ingestion

# Ensure all functions are registered
__all__ = ["FUNCTION_DECLARATIONS", "execute_function", "register_function"]
