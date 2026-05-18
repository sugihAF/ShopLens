"""Tests for ChatService cancellation support."""
import asyncio
import inspect

import pytest

from app.services.chat_service import ChatService
from app.services.chat_exceptions import ChatCancelled
from app.schemas.chat import ChatRequest


@pytest.mark.asyncio
async def test_current_conversation_id_starts_none(db_session):
    """ChatService exposes current_conversation_id, initially None."""
    service = ChatService(db_session)
    assert service.current_conversation_id is None


@pytest.mark.asyncio
async def test_process_message_accepts_cancel_event_and_on_question(db_session):
    """process_message has cancel_event and on_question kwargs (plumbing only)."""
    service = ChatService(db_session)
    sig = inspect.signature(service.process_message)
    assert "cancel_event" in sig.parameters
    assert "on_question" in sig.parameters


@pytest.mark.asyncio
async def test_cancel_event_raises_at_loop_boundary(db_session, monkeypatch):
    """If cancel_event is set before the function loop iterates, ChatCancelled is raised."""
    service = ChatService(db_session)
    if service.provider is None:
        pytest.skip("LLM provider not initialized in test environment")

    sentinel_response = object()

    async def fake_generate(contents, config):
        return sentinel_response

    def fake_has_function_call(response):
        return True

    def fake_build_config(**kw):
        return None

    def fake_build_content(role, msg):
        return {"role": role, "text": msg}

    monkeypatch.setattr(service.provider, "generate", fake_generate)
    monkeypatch.setattr(service.provider, "has_function_call", fake_has_function_call)
    monkeypatch.setattr(service.provider, "build_config", fake_build_config)
    monkeypatch.setattr(service.provider, "build_content", fake_build_content)

    cancel_event = asyncio.Event()
    cancel_event.set()

    request = ChatRequest(message="hi", conversation_id=None)

    with pytest.raises(ChatCancelled) as excinfo:
        await service.process_message(
            request, user_id=None, cancel_event=cancel_event
        )

    assert excinfo.value.reason == "user"
    assert excinfo.value.conversation_id is not None
