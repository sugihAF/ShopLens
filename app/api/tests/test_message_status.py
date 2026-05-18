"""Tests for Message.status column and MessageStatus enum."""
import pytest

from app.models.conversation import Conversation, Message, MessageRole, MessageStatus


@pytest.mark.asyncio
async def test_message_defaults_to_complete_status(db_session):
    conv = Conversation()
    db_session.add(conv)
    await db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content="hello",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.refresh(msg)

    assert msg.status == MessageStatus.COMPLETE


@pytest.mark.asyncio
async def test_message_can_be_cancelled(db_session):
    conv = Conversation()
    db_session.add(conv)
    await db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content="",
        status=MessageStatus.CANCELLED,
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.refresh(msg)

    assert msg.status == MessageStatus.CANCELLED
