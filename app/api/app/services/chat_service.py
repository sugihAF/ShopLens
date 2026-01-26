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

## Your Capabilities:
- Search for products across categories (smartphones, laptops, headphones, tablets, etc.)
- Provide review summaries from trusted tech reviewers like MKBHD, Linus Tech Tips, Dave2D, etc.
- Show reviewer consensus (what they agree/disagree on about a product)
- Compare multiple products side-by-side
- Find where to buy products at the best prices
- Answer specific questions about product features based on reviewer opinions

## Guidelines:
1. **Always cite sources**: When sharing information from reviews, mention which reviewer said it
2. **Be objective**: Present multiple viewpoints when reviewers disagree
3. **Use data**: Call the appropriate functions to get real data - never make up information
4. **Be helpful**: If you don't have data on a product, honestly say so and suggest alternatives
5. **Be concise**: Give clear, direct answers. Expand only when the user asks for details
6. **Highlight trade-offs**: When comparing products, clearly explain the pros and cons of each

## Response Format:
- Use markdown for better readability
- Use bullet points for lists
- Bold important points
- When showing multiple products, format them clearly

## Tone:
Helpful, knowledgeable, and conversational but concise. Like talking to a tech-savvy friend who has done the research for you.

Remember: You help people make better purchasing decisions by synthesizing information from expert reviewers. Your goal is to save them time while ensuring they have accurate information."""


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

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            final_response = "I'm sorry, I encountered an error processing your request. Please try again."
            functions_called = []

        execution_time = int((time.time() - start_time) * 1000)

        # Extract sources and attachments from function results
        sources = self._extract_sources(functions_called, conversation.context)
        attachments = self._extract_attachments(functions_called, conversation.context)

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
            parts = response.candidates[0].content.parts
            if not parts:
                return False
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
            parts = response.candidates[0].content.parts
            for part in parts:
                if hasattr(part, 'function_call') and part.function_call:
                    return part
            return None
        except (AttributeError, IndexError):
            return None

    def _extract_text(self, response) -> str:
        """Extract text content from response."""
        try:
            for part in response.candidates[0].content.parts:
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
        functions_called: List[str],
        context: Optional[Dict]
    ) -> List[Attachment]:
        """Extract attachments based on functions called."""
        attachments = []
        # Attachments like comparison tables would be generated here
        # For now, return empty list - will be enhanced with actual data
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
