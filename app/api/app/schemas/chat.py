"""Chat-related schemas for the API."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Message role enum."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# === Request Schemas ===

class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[UUID] = None  # None creates new conversation

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Compare iPhone 15 Pro and Samsung Galaxy S24 Ultra",
                "conversation_id": None
            }
        }
    }


class MessageFeedbackRequest(BaseModel):
    """User feedback on a message."""
    rating: int = Field(..., ge=1, le=5)
    feedback_text: Optional[str] = Field(None, max_length=1000)


# === Response Schemas ===

class SourceReference(BaseModel):
    """Reference to source material."""
    type: str  # "review", "product", "reviewer"
    id: int
    name: str
    url: Optional[str] = None
    snippet: Optional[str] = None


class Attachment(BaseModel):
    """Rich content attachment."""
    type: str  # "comparison_table", "product_card", "price_chart"
    data: Dict[str, Any]


class MessageResponse(BaseModel):
    """Response schema for a message."""
    id: UUID
    role: MessageRole
    content: str
    sources: Optional[List[SourceReference]] = None
    attachments: Optional[List[Attachment]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    """Response to a chat message."""
    message: MessageResponse
    conversation_id: UUID
    suggested_questions: Optional[List[str]] = None
    products_mentioned: Optional[List[int]] = None


class ConversationResponse(BaseModel):
    """Conversation summary response."""
    id: UUID
    title: Optional[str]
    summary: Optional[str]
    message_count: int
    created_at: datetime
    last_message_at: Optional[datetime]
    products_discussed: List[int] = []

    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    """Full conversation with messages."""
    messages: List[MessageResponse]
    context: Dict[str, Any] = {}


class ConversationListResponse(BaseModel):
    """Paginated list of conversations."""
    conversations: List[ConversationResponse]
    total: int
    page: int
    per_page: int
    has_more: bool
