"""Chat service with Gemini function calling integration."""

import json
import time
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging import get_logger
from app.crud.conversation import conversation_crud
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    SourceReference,
    Attachment,
)
from app.functions.registry import FUNCTION_DECLARATIONS, execute_function

logger = get_logger(__name__)

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
- For EACH URL returned, call `ingest_youtube_review(video_url, product_name)`
- Call `search_blog_reviews(product_name, limit=2)` to find blog review URLs
- For EACH URL returned, call `ingest_blog_review(url, product_name)`
- Skip any URLs that fail and continue with others
- After all ingestion is done, call `get_reviews_summary(product_name)`

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
- `ingest_youtube_review(video_url, product_name)` - Analyze and store YouTube review
- `search_blog_reviews(product_name, limit)` - Find blog review URLs
- `ingest_blog_review(url, product_name)` - Scrape and store blog review
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
    Main chat service using Gemini with function calling.

    Handles:
    - Conversation management
    - Gemini API integration
    - Function calling loop
    - Response formatting
    """

    def __init__(self, db: AsyncSession):
        """Initialize chat service with database session."""
        self.db = db
        self.client = None
        self.tools = None
        self._init_gemini()

    def _init_gemini(self):
        """Initialize Gemini client and tools."""
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set - chat will not work")
            return

        try:
            # Initialize the new genai client
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

            # Convert function declarations to the new format
            function_declarations = []
            for func in FUNCTION_DECLARATIONS:
                # Build properties dict for the schema
                properties = {}
                for param_name, param_schema in func["parameters"]["properties"].items():
                    properties[param_name] = self._convert_param_schema(param_schema)

                func_decl = types.FunctionDeclaration(
                    name=func["name"],
                    description=func["description"],
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties=properties,
                        required=func["parameters"].get("required", [])
                    )
                )
                function_declarations.append(func_decl)

            # Create tools with function declarations
            self.tools = [types.Tool(function_declarations=function_declarations)]

            logger.info("Gemini client initialized successfully with function calling")

        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}", exc_info=True)
            self.client = None

    def _convert_param_schema(self, param: Dict[str, Any]) -> types.Schema:
        """Convert parameter schema to Gemini types.Schema format."""
        type_mapping = {
            "string": types.Type.STRING,
            "integer": types.Type.INTEGER,
            "number": types.Type.NUMBER,
            "boolean": types.Type.BOOLEAN,
            "array": types.Type.ARRAY,
            "object": types.Type.OBJECT,
        }

        schema_type = type_mapping.get(param.get("type", "string"), types.Type.STRING)

        schema_kwargs = {
            "type": schema_type,
        }

        if "description" in param:
            schema_kwargs["description"] = param["description"]

        if "enum" in param:
            schema_kwargs["enum"] = param["enum"]

        if param.get("type") == "array" and "items" in param:
            items_type = type_mapping.get(param["items"].get("type", "string"), types.Type.STRING)
            schema_kwargs["items"] = types.Schema(type=items_type)

        return types.Schema(**schema_kwargs)

    async def process_message(
        self,
        request: ChatRequest,
        user_id: Optional[int] = None
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
        # Check if client is initialized
        if self.client is None:
            raise RuntimeError(
                "Gemini client is not initialized. Please check that GEMINI_API_KEY is set correctly."
            )

        start_time = time.time()
        functions_called = []
        function_results = []  # Store function results for attachment extraction

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
            # Create content configuration
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=self.tools,
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=2048,
            )

            # Build contents list with history
            contents = list(history) if history else []

            # Add user message
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=request.message)]
            ))

            # Initial request
            response = await self.client.aio.models.generate_content(
                model=settings.LLM_MODEL,
                contents=contents,
                config=config
            )

            # Handle function calling loop with thought_signature preservation
            while self._has_function_call(response):
                # Extract function call and thought_signature from the same part
                function_call_part = self._extract_function_call_part(response)
                if not function_call_part or not function_call_part.function_call:
                    break

                function_call = function_call_part.function_call
                function_name = function_call.name
                function_args = dict(function_call.args) if function_call.args else {}
                functions_called.append(function_name)

                logger.info(f"Calling function: {function_name} with args: {function_args}")

                # Execute the function
                function_result = await execute_function(
                    self.db,
                    function_name,
                    function_args
                )

                # Store function result for attachment extraction
                function_results.append({
                    "name": function_name,
                    "args": function_args,
                    "result": function_result
                })

                # CRITICAL: Append the complete model response to preserve thought_signature
                # The model's content includes the function_call part WITH thought_signature
                model_content = response.candidates[0].content
                contents.append(model_content)

                # Extract thought_signature from the function call part
                # Requires google-genai SDK >= 1.50.0 for Gemini 3 thought_signature support
                thought_sig = getattr(function_call_part, 'thought_signature', None)

                # Create function response with thought_signature if present
                if thought_sig:
                    # Manually construct Part with thought_signature
                    function_response_part = types.Part(
                        function_response=types.FunctionResponse(
                            name=function_name,
                            response={"result": json.dumps(function_result)}
                        ),
                        thought_signature=thought_sig
                    )
                else:
                    # Fallback: Create function response without thought_signature
                    # Note: This may cause issues with Gemini 3 models
                    function_response_part = types.Part.from_function_response(
                        name=function_name,
                        response={"result": json.dumps(function_result)}
                    )

                # Add function response
                contents.append(types.Content(
                    role="user",
                    parts=[function_response_part]
                ))

                # Send updated contents back to model
                response = await self.client.aio.models.generate_content(
                    model=settings.LLM_MODEL,
                    contents=contents,
                    config=config
                )

            # Extract final text response
            final_response = self._extract_text(response)

            # Log warning if no functions were called for a product question
            if not functions_called and self._looks_like_product_question(request.message):
                logger.warning(
                    f"No function calls made for what appears to be a product question: {request.message[:100]}"
                )

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
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
                "model": settings.LLM_MODEL,
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

    async def _build_chat_history(self, conversation_id: UUID) -> List[types.Content]:
        """Build chat history in Gemini format."""
        messages = await conversation_crud.get_recent_messages(
            self.db,
            conversation_id=conversation_id,
            limit=20  # Last 20 messages for context
        )

        history = []
        for msg in messages:
            role = "user" if msg.role.value == "user" else "model"
            history.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg.content)]
                )
            )

        return history

    async def _build_chat_history_excluding_last(self, conversation_id: UUID) -> List[types.Content]:
        """Build chat history excluding the most recent message (to avoid duplicates).

        This is used when we've just saved the user's message to the database
        but will send it separately to the chat interface.
        """
        messages = await conversation_crud.get_recent_messages(
            self.db,
            conversation_id=conversation_id,
            limit=21  # Get one extra to account for excluding the last
        )

        # Exclude the most recent message (which we'll send separately)
        if messages:
            messages = messages[1:]  # Skip the first (most recent) message

        history = []
        for msg in messages:
            role = "user" if msg.role.value == "user" else "model"
            history.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg.content)]
                )
            )

        return history

    def _has_function_call(self, response) -> bool:
        """Check if response contains a function call."""
        try:
            if not response.candidates:
                return False
            content = response.candidates[0].content
            if not content or not content.parts:
                return False
            parts = content.parts
            return hasattr(parts[0], 'function_call') and parts[0].function_call and parts[0].function_call.name
        except (AttributeError, IndexError):
            return False

    def _extract_function_call(self, response):
        """Extract function call from response."""
        try:
            return response.candidates[0].content.parts[0].function_call
        except (AttributeError, IndexError):
            return None

    def _extract_function_call_part(self, response):
        """Extract the Part containing the function call (includes thought_signature)."""
        try:
            if not response.candidates:
                return None
            content = response.candidates[0].content
            if not content or not content.parts:
                return None
            for part in content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    return part
            return None
        except (AttributeError, IndexError):
            return None

    def _extract_text(self, response) -> str:
        """Extract text content from response."""
        try:
            if not response.candidates:
                return ""
            content = response.candidates[0].content
            if not content or not content.parts:
                return ""
            for part in content.parts:
                if hasattr(part, 'text') and part.text:
                    return part.text
            return ""
        except (AttributeError, IndexError):
            return ""

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
                        "summary": summary.get("summary", "")[:300],  # Truncate for card
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
