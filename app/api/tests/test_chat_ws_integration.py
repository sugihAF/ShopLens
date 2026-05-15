"""Integration test for WS /api/v1/chat/ws via FastAPI TestClient.

NOTE: Skipped pending starlette upgrade. starlette 0.35.1 (current pin) +
httpx 0.28.1 are incompatible for WebSocket testing via TestClient — the
TestClient passes `app=` to httpx.Client which 0.28+ removed. Fixed in
starlette 0.36+ which uses ASGITransport. Until then, protocol coverage
lives in test_chat_ws_session.py (unit tests with FakeWebSocket).
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.schemas.chat import ChatResponse, MessageResponse


@pytest.mark.skip(reason="starlette 0.35.1 + httpx 0.28.1 TestClient.websocket_connect incompat; upgrade starlette to fix")
def test_ws_chat_happy_path(db_session, monkeypatch):
    from fastapi.testclient import TestClient
    from app.db.session import get_db
    from app.main import create_application

    test_app = create_application()

    @asynccontextmanager
    async def test_lifespan(app):
        yield

    test_app.router.lifespan_context = test_lifespan

    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db

    @asynccontextmanager
    async def fake_session_factory():
        yield db_session

    # Patch the module-level factory so the WS endpoint uses our test session.
    import app.api.v1.endpoints.chat_ws as chat_ws_module
    monkeypatch.setattr(chat_ws_module, "_db_session_factory", fake_session_factory)

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        if on_progress:
            await on_progress({"type": "progress", "step": "x", "status": "running"})
        return ChatResponse(
            conversation_id=uuid4(),
            message=MessageResponse(
                id=uuid4(),
                role="assistant",
                content="hi",
                created_at=datetime.now(timezone.utc),
            ),
            sources=[],
            attachments=[],
            functions_called=[],
        )

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    with TestClient(test_app) as client:
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({"type": "auth", "token": None})
            ready = ws.receive_json()
            assert ready["type"] == "ready"

            ws.send_json({"type": "message", "request_id": "r1", "text": "hello"})

            seen_complete = False
            for _ in range(20):
                event = ws.receive_json()
                if event["type"] == "complete":
                    assert event["request_id"] == "r1"
                    seen_complete = True
                    break
            assert seen_complete
