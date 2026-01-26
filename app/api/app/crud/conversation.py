"""CRUD operations for Conversation and Message models."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.conversation import Conversation, Message, MessageRole, ConversationStatus
from app.schemas.common import Message as MessageSchema


class ConversationCreate(MessageSchema):
    """Schema for creating conversation (simplified)."""
    pass


class ConversationUpdate(MessageSchema):
    """Schema for updating conversation (simplified)."""
    pass


class CRUDConversation(CRUDBase[Conversation, ConversationCreate, ConversationUpdate]):
    """CRUD operations for Conversation model."""

    async def get(
        self,
        db: AsyncSession,
        id: UUID
    ) -> Optional[Conversation]:
        """Get conversation by UUID."""
        result = await db.execute(
            select(Conversation).where(Conversation.id == id)
        )
        return result.scalar_one_or_none()

    async def get_with_messages(
        self,
        db: AsyncSession,
        id: UUID,
        message_limit: int = 50
    ) -> Optional[Conversation]:
        """Get conversation with messages loaded."""
        result = await db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == id)
        )
        conversation = result.scalar_one_or_none()

        # Limit messages if needed (already ordered by created_at)
        if conversation and len(conversation.messages) > message_limit:
            conversation.messages = conversation.messages[-message_limit:]

        return conversation

    async def create_conversation(
        self,
        db: AsyncSession,
        user_id: Optional[int] = None,
        title: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            user_id=user_id,
            title=title,
            metadata=metadata or {},
            context={}
        )
        db.add(conversation)
        await db.flush()
        await db.refresh(conversation)
        return conversation

    async def get_user_conversations(
        self,
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 20
    ) -> List[Conversation]:
        """Get conversations for a user."""
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.status == ConversationStatus.ACTIVE)
            .order_by(Conversation.last_message_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_user_conversations(
        self,
        db: AsyncSession,
        user_id: int
    ) -> int:
        """Count user's active conversations."""
        result = await db.execute(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.status == ConversationStatus.ACTIVE)
        )
        return result.scalar_one()

    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        role: str,
        content: str,
        intent: Optional[dict] = None,
        agent_metadata: Optional[dict] = None,
        sources: Optional[dict] = None,
        attachments: Optional[dict] = None
    ) -> Message:
        """Add a message to a conversation."""
        message = Message(
            conversation_id=conversation_id,
            role=MessageRole(role),
            content=content,
            intent=intent,
            agent_metadata=agent_metadata,
            sources=sources,
            attachments=attachments
        )
        db.add(message)

        # Update conversation's last_message_at
        conversation = await self.get(db, id=conversation_id)
        if conversation:
            conversation.last_message_at = datetime.now(timezone.utc)
            db.add(conversation)

        await db.flush()
        await db.refresh(message)
        return message

    async def get_messages(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        limit: int = 50
    ) -> List[Message]:
        """Get messages for a conversation."""
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_messages(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        limit: int = 20
    ) -> List[Message]:
        """Get most recent messages (for chat context)."""
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        return list(reversed(messages))  # Return in chronological order

    async def update_context(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        context: Dict[str, Any]
    ) -> Optional[Conversation]:
        """Update conversation context."""
        conversation = await self.get(db, id=conversation_id)
        if conversation:
            # Merge with existing context
            existing = conversation.context or {}
            existing.update(context)
            conversation.context = existing
            db.add(conversation)
            await db.flush()
            await db.refresh(conversation)
        return conversation

    async def archive_conversation(
        self,
        db: AsyncSession,
        conversation_id: UUID
    ) -> Optional[Conversation]:
        """Archive a conversation."""
        conversation = await self.get(db, id=conversation_id)
        if conversation:
            conversation.status = ConversationStatus.ARCHIVED
            db.add(conversation)
            await db.flush()
            await db.refresh(conversation)
        return conversation

    async def delete_conversation(
        self,
        db: AsyncSession,
        conversation_id: UUID
    ) -> bool:
        """Soft delete a conversation."""
        conversation = await self.get(db, id=conversation_id)
        if conversation:
            conversation.status = ConversationStatus.DELETED
            db.add(conversation)
            await db.flush()
            return True
        return False


conversation_crud = CRUDConversation(Conversation)
