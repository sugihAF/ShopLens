"""Conversation and Message models for chat history."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List
import uuid
import enum

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base, UUID, JSONB

if TYPE_CHECKING:
    from app.models.user import User


class ConversationStatus(str, enum.Enum):
    """Status of a conversation."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MessageRole(str, enum.Enum):
    """Role of message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base):
    """Conversation model representing a chat session."""
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Conversation metadata
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus),
        default=ConversationStatus.ACTIVE
    )

    # Context tracking for conversation continuity
    context: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Example context:
    # {
    #   "products_discussed": [1, 5, 23],
    #   "comparison_mode": true,
    #   "user_preferences": {"budget": 1000, "use_case": "gaming"},
    #   "resolved_entities": {"the laptop": 5}
    # }

    # AI-generated summary of conversation
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Additional metadata
    conversation_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Example: {"source": "web", "device": "mobile", "language": "en"}

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now()
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    # Indexes
    __table_args__ = (
        Index('ix_conversations_user_last_message', 'user_id', 'last_message_at'),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id})>"


class Message(Base):
    """Message model representing a single message in a conversation."""
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Message content
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # AI processing metadata (for assistant messages)
    intent: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Example intent:
    # {
    #   "type": "product_comparison",
    #   "entities": {"products": ["iPhone 15", "Galaxy S24"]},
    #   "constraints": {"budget": 1000}
    # }

    agent_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Example agent_metadata:
    # {
    #   "model": "gemini/gemini-2.0-flash",
    #   "functions_called": ["search_products", "compare_products"],
    #   "execution_time_ms": 1250,
    #   "tokens_used": {"prompt": 500, "completion": 200}
    # }

    # Sources and citations
    sources: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Example sources:
    # [
    #   {"type": "review", "id": 123, "reviewer": "MKBHD", "url": "..."},
    #   {"type": "product", "id": 5, "name": "iPhone 15 Pro"}
    # ]

    # Rich content attachments
    attachments: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Example attachments:
    # [
    #   {"type": "comparison_table", "data": {...}},
    #   {"type": "product_card", "product_id": 5}
    # ]

    # User feedback
    feedback_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages"
    )

    # Indexes
    __table_args__ = (
        Index('ix_messages_conversation_created', 'conversation_id', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"
