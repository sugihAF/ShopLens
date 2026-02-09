"""Chat endpoint - main AI interaction point."""

import asyncio
import json
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
    ConversationDetailResponse,
    ConversationResponse,
    MessageFeedbackRequest,
)
from app.schemas.common import Message
from app.crud.conversation import conversation_crud
from app.core.security import get_current_user_id
from app.services.chat_service import ChatService
from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def send_chat_message(
    request: Request,
    chat_request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = Depends(get_current_user_id)
):
    """
    Send a chat message and get AI response.

    This is the main endpoint for all chat interactions.
    The AI will use function calling to:
    - Search for products
    - Get product details and reviews
    - Compare products
    - Find marketplace listings
    - And more...

    Conversation history is automatically maintained.
    """
    try:
        chat_service = ChatService(db)
        response = await chat_service.process_message(chat_request, user_id=user_id)
        return response

    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message. Please try again."
        )


@router.post("/stream")
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def stream_chat_message(
    request: Request,
    chat_request: ChatRequest,
    user_id: Optional[int] = Depends(get_current_user_id),
):
    """
    Stream a chat message with real-time progress events via SSE.

    Sends progress events as each pipeline function starts/completes,
    then sends the final complete response.

    Note: This endpoint manages its own database session inside the
    generator rather than using Depends(get_db), because FastAPI closes
    dependency-injected resources when the endpoint returns — before
    StreamingResponse finishes iterating.
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def on_progress(event: dict):
        await queue.put(event)

    async def run_chat():
        """Run process_message with its own DB session inside the task."""
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            try:
                chat_service = ChatService(db)
                result = await chat_service.process_message(
                    chat_request, user_id=user_id, on_progress=on_progress
                )
                await queue.put({"type": "complete", "data": result.model_dump(mode="json")})
            except Exception as e:
                logger.error(f"Stream chat error: {e}", exc_info=True)
                await queue.put({"type": "error", "message": "Failed to process chat message. Please try again."})

    async def generate():
        task = asyncio.create_task(run_chat())

        while not task.done():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                continue

        # Drain any remaining queued events
        while not queue.empty():
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    List user's conversations.
    Requires authentication.
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    skip = (page - 1) * per_page
    conversations = await conversation_crud.get_user_conversations(
        db,
        user_id=user_id,
        skip=skip,
        limit=per_page
    )
    total = await conversation_crud.count_user_conversations(db, user_id=user_id)

    # Convert to response format
    conversation_responses = []
    for conv in conversations:
        messages = await conversation_crud.get_messages(db, conversation_id=conv.id, limit=1)
        conversation_responses.append(
            ConversationResponse(
                id=conv.id,
                title=conv.title,
                summary=conv.summary,
                message_count=len(conv.messages) if conv.messages else 0,
                created_at=conv.created_at,
                last_message_at=conv.last_message_at,
                products_discussed=conv.context.get("products_discussed", []) if conv.context else []
            )
        )

    return ConversationListResponse(
        conversations=conversation_responses,
        total=total,
        page=page,
        per_page=per_page,
        has_more=(page * per_page) < total
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = Depends(get_current_user_id)
):
    """
    Get a specific conversation with messages.
    """
    conversation = await conversation_crud.get_with_messages(db, id=conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Check ownership if user is authenticated
    if user_id and conversation.user_id and conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        summary=conversation.summary,
        message_count=len(conversation.messages),
        created_at=conversation.created_at,
        last_message_at=conversation.last_message_at,
        products_discussed=conversation.context.get("products_discussed", []) if conversation.context else [],
        messages=[
            {
                "id": msg.id,
                "role": msg.role.value,
                "content": msg.content,
                "sources": msg.sources,
                "attachments": msg.attachments,
                "created_at": msg.created_at
            }
            for msg in conversation.messages
        ],
        context=conversation.context or {}
    )


@router.delete("/conversations/{conversation_id}", response_model=Message)
async def delete_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Delete a conversation (soft delete).
    Requires authentication.
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    conversation = await conversation_crud.get(db, id=conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    if conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    await conversation_crud.delete_conversation(db, conversation_id=conversation_id)

    return Message(message="Conversation deleted")


@router.post("/conversations/{conversation_id}/messages/{message_id}/feedback")
async def submit_feedback(
    conversation_id: UUID,
    message_id: UUID,
    feedback: MessageFeedbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit feedback on a message.
    """
    # Get the message and update feedback
    from sqlalchemy import select, update
    from app.models.conversation import Message as MessageModel

    result = await db.execute(
        select(MessageModel).where(
            MessageModel.id == message_id,
            MessageModel.conversation_id == conversation_id
        )
    )
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    message.feedback_rating = feedback.rating
    message.feedback_text = feedback.feedback_text
    db.add(message)
    await db.flush()

    return Message(message="Feedback submitted")
