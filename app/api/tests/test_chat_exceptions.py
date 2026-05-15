"""Tests for chat exception types."""
import pytest

from app.services.chat_exceptions import ChatCancelled, QuestionTimeout


def test_chat_cancelled_carries_conversation_id():
    exc = ChatCancelled(conversation_id="abc-123", reason="user")
    assert exc.conversation_id == "abc-123"
    assert exc.reason == "user"
    assert "user" in str(exc)


def test_chat_cancelled_default_reason_is_user():
    exc = ChatCancelled(conversation_id="abc-123")
    assert exc.reason == "user"


def test_question_timeout_is_an_exception():
    with pytest.raises(QuestionTimeout):
        raise QuestionTimeout("no answer in 60s")
