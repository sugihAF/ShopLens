"""Chat service with multi-provider LLM function calling integration."""

import json
import time
from typing import Optional, List, Dict, Any, Callable, Awaitable
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.circuit_breaker import gemini_breaker
from app.core.logging import (
    get_logger, log_header, log_success, log_fail, log_detail, elapsed_str,
    BOLD, CYAN, DIM, GREEN, YELLOW, MAGENTA, RESET, LINE,
)
from app.crud.conversation import conversation_crud
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    SourceReference,
    Attachment,
)
from app.functions.registry import FUNCTION_DECLARATIONS, execute_function
from app.services.llm_service import get_llm_provider, BaseLLMProvider

logger = get_logger(__name__)

# Safety limit for function calling loop iterations
MAX_FUNCTION_CALL_ITERATIONS = 25

# Human-readable labels for function calling progress events
FUNCTION_LABELS = {
    "check_product_cache": "Checking product cache",
    "search_youtube_reviews": "Searching YouTube",
    "search_blog_reviews": "Searching blog reviews",
    "ingest_reviews_batch": "Analyzing reviews",
    "ingest_youtube_review": "Analyzing YouTube review",
    "ingest_blog_review": "Analyzing blog review",
    "get_reviews_summary": "Generating summary",
    "find_marketplace_listings": "Finding where to buy",
    "compare_products": "Comparing products",
    "search_products": "Searching products",
    "get_product_reviews": "Fetching reviews",
    "semantic_search": "Searching knowledge base",
}

# System prompt for ShopLens AI
SYSTEM_PROMPT = """You are ShopLens, an AI assistant that helps users make informed purchasing decisions by aggregating and analyzing product reviews from trusted tech reviewers on YouTube and tech blogs.

## CRITICAL RULES - READ FIRST:
1. **NEVER answer from your training data** - You must ONLY use information returned by function calls
2. **ALWAYS call functions** when the user asks about a product - follow the flow below
3. **If no data is available**, search for new reviews using the tools
4. **ALWAYS cite sources** - Format: "According to MKBHD..." or "The Verge says..."
5. **NEVER make up** product specifications, prices, or reviewer opinions

## REVIEW FLOW - Follow These Steps:

### Step 1: Check Cache First
When user asks about a product (e.g., "Tell me about Samsung Galaxy S25"):
- Call `check_product_cache(product_name)` FIRST
- If status="found" with reviews:
  1. Call `get_reviews_summary(product_name)`
  2. **STOP calling functions** and write your text response based on the summary data
  3. Do NOT call search_youtube_reviews or other functions - the data is already cached
- If status="not_found" or "no_reviews", proceed to Step 2

### Step 2: Gather New Reviews (ONLY if not in cache)
- Call `search_youtube_reviews(product_name, limit=3)` to find YouTube review URLs
- Call `search_blog_reviews(product_name, limit=2)` to find blog review URLs
- Call `ingest_reviews_batch(product_name, youtube_urls=[...], blog_urls=[...])` ONCE with ALL URLs from both searches — this ingests them in parallel and is much faster than calling individually
- After batch ingestion is done, call `get_reviews_summary(product_name)`
- IMPORTANT: Do NOT call `ingest_youtube_review` or `ingest_blog_review` individually — always use `ingest_reviews_batch` for efficiency

### Step 3: Present Summary (ALWAYS ends with text response)
After calling `get_reviews_summary`:
- **STOP calling functions immediately**
- Write a comprehensive text response using the summary data
- Present per-reviewer summaries (paragraph for each reviewer)
- Present the overall product summary
- Mention common pros and cons

### Step 4: Marketplace (when asked)
- When user asks "where can I buy" or about prices
- Call `find_marketplace_listings(product_name, count_per_marketplace=2)`
- Present Amazon and eBay links with prices

## Function Reference:
- `check_product_cache(product_name)` - Check if we have cached reviews
- `search_youtube_reviews(product_name, limit)` - Find YouTube review URLs
- `search_blog_reviews(product_name, limit)` - Find blog review URLs
- `ingest_reviews_batch(product_name, youtube_urls, blog_urls)` - Ingest all reviews in parallel (PREFERRED)
- `ingest_youtube_review(video_url, product_name)` - Analyze and store YouTube review (fallback only)
- `ingest_blog_review(url, product_name)` - Scrape and store blog review (fallback only)
- `get_reviews_summary(product_name)` - Get per-reviewer and overall summaries
- `find_marketplace_listings(product_name, count_per_marketplace)` - Find where to buy

## Guidelines:
1. **Always cite sources**: When sharing information, mention which reviewer said it
2. **Be thorough**: Present detailed paragraph summaries for each reviewer
3. **Be objective**: Present multiple viewpoints when reviewers disagree
4. **Use data**: Call the appropriate functions - never make up information
5. **Handle errors gracefully**: If some URLs fail, continue with others

## Response Format:
- Use markdown for better readability
- Present each reviewer's summary as a full paragraph (not just bullet points)
- Bold reviewer names and key points
- Include links to original reviews when available

## Tone:
Helpful, knowledgeable, and conversational. Like talking to a tech-savvy friend who has done the research for you.

## CRITICAL REMINDER:
- After calling `get_reviews_summary`, you MUST generate a text response - do NOT call any more functions
- The text response should summarize the review data in a helpful, conversational way
- If cache has reviews, you do NOT need to search for more - just use `get_reviews_summary` and respond"""


class ChatService:
    """
    Main chat service with multi-provider LLM function calling.

    Handles:
    - Conversation management
    - LLM provider abstraction (Gemini / OpenAI)
    - Function calling loop
    - Response formatting
    """

    def __init__(self, db: AsyncSession):
        """Initialize chat service with database session."""
        self.db = db
        self.provider: Optional[BaseLLMProvider] = None
        self.tools = None
        self._init_provider()

    def _init_provider(self):
        """Initialize LLM provider and tools."""
        try:
            self.provider = get_llm_provider()
            self.tools = self.provider.convert_function_declarations(FUNCTION_DECLARATIONS)
            logger.info(f"LLM provider initialized: {settings.LLM_PROVIDER}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM provider: {e}", exc_info=True)
            self.provider = None

    async def process_message(
        self,
        request: ChatRequest,
        user_id: Optional[int] = None,
        on_progress: Optional[Callable[[Dict[str, str]], Awaitable[None]]] = None,
    ) -> ChatResponse:
        """
        Process a chat message using Gemini with function calling.

        Handles thought_signature preservation for Gemini 3 models by extracting
        and passing it explicitly with function responses.

        Args:
            request: Chat request with message and optional conversation_id
            user_id: Optional authenticated user ID

        Returns:
            ChatResponse with AI response and metadata
        """
        # Check if provider is initialized
        if self.provider is None:
            raise RuntimeError(
                "LLM provider is not initialized. Please check your API keys and LLM_PROVIDER setting."
            )

        start_time = time.time()
        functions_called = []
        function_results = []  # Store function results for attachment extraction
        fn_step = 0

        logger.info(f"{LINE}")
        logger.info(f"{BOLD}{MAGENTA}Chat{RESET} │ {request.message[:80]}")

        # Get or create conversation
        conversation = None
        if request.conversation_id:
            conversation = await conversation_crud.get(self.db, id=request.conversation_id)

        if not conversation:
            conversation = await conversation_crud.create_conversation(
                self.db,
                user_id=user_id,
                title=self._generate_title(request.message)
            )

        # Save user message
        user_message = await conversation_crud.add_message(
            self.db,
            conversation_id=conversation.id,
            role="user",
            content=request.message
        )

        # Get conversation history for context (excluding the message we just saved)
        history = await self._build_chat_history_excluding_last(conversation.id)

        try:
            # Check circuit breaker before making Gemini calls
            if not gemini_breaker.allow_request():
                logger.warning("Gemini circuit breaker is OPEN — returning graceful error")
                final_response = (
                    "I'm currently experiencing issues connecting to the AI service. "
                    "Please try again in a moment."
                )
                execution_time = int((time.time() - start_time) * 1000)
                sources = []
                attachments = []

                assistant_message = await conversation_crud.add_message(
                    self.db,
                    conversation_id=conversation.id,
                    role="assistant",
                    content=final_response,
                    agent_metadata={
                        "model": settings.LLM_MODEL,
                        "functions_called": [],
                        "execution_time_ms": execution_time,
                        "circuit_breaker": "open",
                    },
                )
                await self._update_conversation_context(conversation.id, [])
                await self.db.commit()

                return ChatResponse(
                    message=MessageResponse(
                        id=assistant_message.id,
                        role="assistant",
                        content=final_response,
                        sources=None,
                        attachments=None,
                        created_at=assistant_message.created_at
                    ),
                    conversation_id=conversation.id
                )

            # Create content configuration via provider
            config = self.provider.build_config(
                system_instruction=SYSTEM_PROMPT,
                tools=self.tools,
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=2048,
            )

            # Build contents list with history
            contents = list(history) if history else []

            # Add user message
            contents.append(self.provider.build_content("user", request.message))

            # Initial request
            try:
                response = await self.provider.generate(contents, config)
                gemini_breaker.record_success()
            except Exception:
                gemini_breaker.record_failure()
                raise

            # Handle function calling loop (provider-agnostic)
            iteration = 0
            while self.provider.has_function_call(response) and iteration < MAX_FUNCTION_CALL_ITERATIONS:
                # Extract function call from response
                fc = self.provider.extract_function_call(response)
                function_call_part = self.provider.extract_function_call_part(response)
                if not fc:
                    break

                function_name = fc["name"]
                function_args = fc["args"]
                functions_called.append(function_name)
                fn_step += 1
                fn_start = time.time()

                # Pretty-print args
                short_args = ", ".join(
                    f"{k}={repr(v)[:40]}" for k, v in function_args.items()
                )
                logger.info(f"{BOLD}{CYAN}[fn {fn_step}]{RESET} {function_name}({short_args})")

                # Emit progress: function starting
                if on_progress:
                    await on_progress({
                        "type": "progress",
                        "step": function_name,
                        "status": "running",
                        "label": FUNCTION_LABELS.get(function_name, function_name),
                    })

                # Execute the function
                function_result = await execute_function(
                    self.db,
                    function_name,
                    function_args
                )

                # Log function result summary
                fn_elapsed = elapsed_str(fn_start)
                result_status = function_result.get("status", "")
                err = function_result.get("error", "")
                if err:
                    logger.info(f"  {YELLOW}⚠{RESET} {err} {fn_elapsed}")
                elif result_status in ("success", "found"):
                    summary_parts = []
                    for key in ("total_reviews", "urls", "videos", "articles", "amazon", "ebay", "reviews"):
                        val = function_result.get(key)
                        if isinstance(val, list) and val:
                            summary_parts.append(f"{len(val)} {key}")
                        elif isinstance(val, (int, float)) and val:
                            summary_parts.append(f"{key}={val}")
                    detail = ", ".join(summary_parts) if summary_parts else result_status
                    logger.info(f"  {GREEN}✓{RESET} {detail} {fn_elapsed}")
                else:
                    logger.info(f"  {DIM}→ {result_status or 'done'}{RESET} {fn_elapsed}")

                # Emit progress: function done
                if on_progress:
                    await on_progress({
                        "type": "progress",
                        "step": function_name,
                        "status": "done",
                        "label": FUNCTION_LABELS.get(function_name, function_name),
                    })

                # Store function result for attachment extraction
                function_results.append({
                    "name": function_name,
                    "args": function_args,
                    "result": function_result
                })

                # Build provider-specific function response items and append to contents
                response_items = self.provider.build_function_response(
                    function_name, function_result, response, function_call_part
                )
                contents.extend(response_items)

                # Send updated contents back to model
                try:
                    response = await self.provider.generate(contents, config)
                    gemini_breaker.record_success()
                except Exception:
                    gemini_breaker.record_failure()
                    raise

                iteration += 1

            # Check if we hit the iteration limit
            if iteration >= MAX_FUNCTION_CALL_ITERATIONS:
                logger.warning(
                    f"Function calling loop hit max iterations ({MAX_FUNCTION_CALL_ITERATIONS}). "
                    f"Functions called: {functions_called}"
                )

            # Emit progress: generating final response
            if on_progress and functions_called:
                await on_progress({
                    "type": "progress",
                    "step": "generating",
                    "status": "running",
                    "label": "Generating response",
                })

            # Extract final text response
            final_response = self.provider.extract_text(response)

            # Fallback message if iteration limit was reached with no text
            if not final_response and iteration >= MAX_FUNCTION_CALL_ITERATIONS:
                final_response = (
                    "I gathered some information but reached my processing limit. "
                    "Please try asking your question again, and I'll do my best to help."
                )

            total_elapsed = elapsed_str(start_time)
            if functions_called:
                logger.info(f"{LINE}")
                logger.info(
                    f"{BOLD}Done{RESET} │ {len(functions_called)} function(s): "
                    f"{', '.join(functions_called)} {total_elapsed}"
                )
            else:
                logger.info(f"{DIM}  text-only response{RESET} {total_elapsed}")

            # Log warning if no functions were called for a product question
            if not functions_called and self._looks_like_product_question(request.message):
                logger.warning(
                    f"No function calls made for what appears to be a product question: {request.message[:100]}"
                )

        except Exception as e:
            logger.error(f"LLM API error: {e}", exc_info=True)
            final_response = "I'm sorry, I encountered an error processing your request. Please try again."
            functions_called = []

        execution_time = int((time.time() - start_time) * 1000)

        # Extract sources and attachments from function results
        sources = self._extract_sources(functions_called, conversation.context)
        attachments = self._extract_attachments(function_results)

        # Save assistant message
        assistant_message = await conversation_crud.add_message(
            self.db,
            conversation_id=conversation.id,
            role="assistant",
            content=final_response,
            agent_metadata={
                "provider": settings.LLM_PROVIDER,
                "model": settings.LLM_MODEL if settings.LLM_PROVIDER == "gemini" else settings.OPENAI_MODEL,
                "functions_called": functions_called,
                "execution_time_ms": execution_time,
            },
            sources={"references": [s.model_dump() for s in sources]} if sources else None,
            attachments={"items": [a.model_dump() for a in attachments]} if attachments else None
        )

        # Update conversation context with products discussed
        await self._update_conversation_context(conversation.id, functions_called)

        # Commit all changes
        await self.db.commit()

        return ChatResponse(
            message=MessageResponse(
                id=assistant_message.id,
                role="assistant",
                content=final_response,
                sources=sources if sources else None,
                attachments=attachments if attachments else None,
                created_at=assistant_message.created_at
            ),
            conversation_id=conversation.id
        )

    async def _build_chat_history(self, conversation_id: UUID) -> List[Any]:
        """Build chat history in provider format."""
        messages = await conversation_crud.get_recent_messages(
            self.db,
            conversation_id=conversation_id,
            limit=20
        )

        history = []
        for msg in messages:
            role = "user" if msg.role.value == "user" else "model"
            history.append(self.provider.build_content(role, msg.content))

        return history

    async def _build_chat_history_excluding_last(self, conversation_id: UUID) -> List[Any]:
        """Build chat history excluding the most recent message (to avoid duplicates)."""
        messages = await conversation_crud.get_recent_messages(
            self.db,
            conversation_id=conversation_id,
            limit=21
        )

        if messages:
            messages = messages[1:]

        history = []
        for msg in messages:
            role = "user" if msg.role.value == "user" else "model"
            history.append(self.provider.build_content(role, msg.content))

        return history

    def _generate_title(self, message: str) -> str:
        """Generate a title for a new conversation."""
        # Simple title generation - take first 50 chars
        title = message[:50].strip()
        if len(message) > 50:
            title += "..."
        return title

    def _looks_like_product_question(self, message: str) -> bool:
        """Check if a message looks like it's asking about a product.

        Used to log warnings if the AI doesn't call a function for product questions.
        """
        message_lower = message.lower()

        # Product question indicators
        product_keywords = [
            "review", "reviews", "opinion", "opinions",
            "tell me about", "what do you think",
            "is it good", "is it worth",
            "should i buy", "recommend",
            "iphone", "samsung", "pixel", "galaxy",
            "macbook", "laptop", "phone", "headphones",
            "airpods", "sony", "bose", "apple",
            "how is the", "what's the battery",
            "camera quality", "performance",
            "compared to", "vs", "versus",
            "where to buy", "where can i buy", "price"
        ]

        return any(keyword in message_lower for keyword in product_keywords)

    def _extract_sources(
        self,
        functions_called: List[str],
        context: Optional[Dict]
    ) -> List[SourceReference]:
        """Extract source references based on functions called."""
        sources = []
        # Sources would be populated based on actual function results
        # For now, return empty list - will be enhanced with actual data
        return sources

    def _extract_attachments(
        self,
        function_results: List[Dict[str, Any]]
    ) -> List[Attachment]:
        """Extract attachments from function results."""
        attachments = []

        for func_result in function_results:
            func_name = func_result.get("name")
            result = func_result.get("result", {})

            # Extract reviewer cards from get_reviews_summary (NEW)
            if func_name == "get_reviews_summary" and result.get("status") == "success":
                reviewer_summaries = result.get("reviewer_summaries", [])

                reviewer_cards = []
                for summary in reviewer_summaries[:5]:
                    platform = summary.get("platform", "unknown")
                    card = {
                        "reviewer_name": summary.get("reviewer_name", "Unknown"),
                        "review_url": summary.get("url", ""),
                        "review_type": "video" if platform == "youtube" else "blog",
                        "summary": summary.get("summary", ""),
                        "rating": None,  # No ratings in new flow
                        "pros": result.get("common_pros", [])[:3],
                        "cons": result.get("common_cons", [])[:3],
                    }
                    reviewer_cards.append(card)

                if reviewer_cards:
                    attachments.append(Attachment(
                        type="reviewer_cards",
                        data={
                            "product_name": result.get("product", {}).get("name", ""),
                            "cards": reviewer_cards
                        }
                    ))

            # Note: check_product_cache card extraction removed to avoid duplicates
            # when get_reviews_summary is also called (which has better summary data)

            # Extract reviewer cards from gather_product_reviews (legacy)
            elif func_name == "gather_product_reviews" and result.get("status") == "success":
                reviews = result.get("reviews", [])

                reviewer_cards = []
                seen_reviewers = set()

                for review in reviews:
                    reviewer = review.get("reviewer", "Unknown")
                    if reviewer in seen_reviewers:
                        continue
                    seen_reviewers.add(reviewer)

                    card = {
                        "reviewer_name": reviewer,
                        "reviewer_id": review.get("reviewer_id"),
                        "review_url": review.get("platform_url"),
                        "review_type": review.get("review_type", "video"),
                        "summary": review.get("summary", ""),
                        "rating": review.get("overall_rating"),
                        "pros": review.get("pros", [])[:3],
                        "cons": review.get("cons", [])[:3],
                    }
                    reviewer_cards.append(card)

                    if len(reviewer_cards) >= 5:
                        break

                if reviewer_cards:
                    attachments.append(Attachment(
                        type="reviewer_cards",
                        data={
                            "product_name": result.get("product", {}).get("name", ""),
                            "cards": reviewer_cards
                        }
                    ))

            # Extract reviewer cards from get_product_reviews (legacy)
            elif func_name == "get_product_reviews" and result.get("reviews"):
                reviews = result.get("reviews", [])

                reviewer_cards = []
                seen_reviewers = set()

                for review in reviews:
                    reviewer = review.get("reviewer", "Unknown")
                    if reviewer in seen_reviewers:
                        continue
                    seen_reviewers.add(reviewer)

                    card = {
                        "reviewer_name": reviewer,
                        "reviewer_id": review.get("reviewer_id"),
                        "review_url": review.get("platform_url"),
                        "review_type": review.get("review_type", "video"),
                        "summary": review.get("summary", ""),
                        "rating": review.get("overall_rating"),
                        "pros": review.get("pros", [])[:3],
                        "cons": review.get("cons", [])[:3],
                    }
                    reviewer_cards.append(card)

                    if len(reviewer_cards) >= 5:
                        break

                if reviewer_cards:
                    attachments.append(Attachment(
                        type="reviewer_cards",
                        data={
                            "product_name": result.get("product", {}).get("name", ""),
                            "cards": reviewer_cards
                        }
                    ))

            # Extract marketplace listings from find_marketplace_listings
            elif func_name == "find_marketplace_listings" and result.get("status") in ("success", "partial"):
                listings = []
                for item in result.get("amazon", []):
                    listings.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "price": item.get("price", ""),
                        "description": item.get("seller", ""),
                        "marketplace": "amazon",
                    })
                for item in result.get("ebay", []):
                    listings.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "price": item.get("price", ""),
                        "description": item.get("condition", ""),
                        "marketplace": "ebay",
                    })
                if listings:
                    attachments.append(Attachment(
                        type="marketplace_listings",
                        data={
                            "product_name": result.get("product_name", ""),
                            "listings": listings,
                        }
                    ))

        return attachments

    async def _update_conversation_context(
        self,
        conversation_id: UUID,
        functions_called: List[str]
    ):
        """Update conversation context based on functions called."""
        # This would track products discussed, comparison mode, etc.
        # For MVP, we'll do minimal tracking
        if "compare_products" in functions_called:
            await conversation_crud.update_context(
                self.db,
                conversation_id=conversation_id,
                context={"comparison_mode": True}
            )
