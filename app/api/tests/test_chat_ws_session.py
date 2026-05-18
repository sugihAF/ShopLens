"""Unit tests for ChatWSSession driven by a fake WebSocket."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import pytest

from app.services.chat_ws_session import ChatWSSession
from app.services.chat_exceptions import ChatCancelled, QuestionTimeout
from app.schemas.chat import ChatResponse, MessageResponse


# ----------------------------------------------------------------- FakeWebSocket


class FakeWebSocket:
    """Minimal stand-in for starlette.WebSocket with queue-based I/O."""

    def __init__(self):
        self._incoming: asyncio.Queue = asyncio.Queue()
        self.sent: list[dict] = []
        self.accepted = False
        self.closed_code: Optional[int] = None

    async def accept(self):
        self.accepted = True

    async def receive_json(self) -> Any:
        msg = await self._incoming.get()
        if msg is None:
            from starlette.websockets import WebSocketDisconnect
            raise WebSocketDisconnect(code=1000)
        return msg

    async def send_json(self, payload: dict):
        self.sent.append(payload)

    async def close(self, code: int = 1000):
        self.closed_code = code

    def push(self, msg: dict):
        self._incoming.put_nowait(msg)

    def disconnect(self):
        self._incoming.put_nowait(None)


def _factory(db_session):
    @asynccontextmanager
    async def _cm():
        yield db_session
    return _cm


def _stub_chat_response() -> ChatResponse:
    return ChatResponse(
        conversation_id=uuid4(),
        message=MessageResponse(
            id=uuid4(),
            role="assistant",
            content="hi back",
            created_at=datetime.now(timezone.utc),
        ),
        sources=[],
        attachments=[],
        functions_called=[],
    )


async def _wait_for(predicate, timeout: float = 1.0, interval: float = 0.01):
    """Poll until predicate() is truthy or timeout elapses."""
    elapsed = 0.0
    while elapsed < timeout:
        if predicate():
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    return False


# ----------------------------------------------------------------- auth tests


@pytest.mark.asyncio
async def test_auth_anonymous_emits_ready(db_session):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=_factory(db_session))
    ws.push({"type": "auth", "token": None})
    ws.disconnect()

    await session.run()

    assert ws.accepted
    ready_events = [e for e in ws.sent if e["type"] == "ready"]
    assert len(ready_events) == 1
    assert ready_events[0]["user_id"] is None


@pytest.mark.asyncio
async def test_auth_timeout_closes_4401(db_session):
    ws = FakeWebSocket()
    session = ChatWSSession(
        ws,
        db_session_factory=_factory(db_session),
        auth_timeout_seconds=0.05,
    )
    # No auth message pushed — wait for timeout.
    await session.run()
    assert ws.closed_code == 4401


@pytest.mark.asyncio
async def test_malformed_first_message_closes_4401(db_session):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=_factory(db_session))
    ws.push({"type": "message", "text": "hi"})  # wrong type before auth
    await session.run()
    assert ws.closed_code == 4401


# ---------------------------------------------------------- message happy path


@pytest.mark.asyncio
async def test_message_happy_path_emits_complete(db_session, monkeypatch):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=_factory(db_session))

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        if on_progress:
            await on_progress({"type": "progress", "step": "search", "status": "running"})
            await on_progress({"type": "progress", "step": "search", "status": "done"})
        return _stub_chat_response()

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "hello"})
        ok = await _wait_for(
            lambda: any(e["type"] == "complete" for e in ws.sent), timeout=2.0
        )
        assert ok, f"no complete event in {ws.sent}"
        ws.disconnect()

    await asyncio.gather(session.run(), driver())

    types = [e["type"] for e in ws.sent]
    assert "ready" in types
    assert types.count("progress") == 2
    complete_events = [e for e in ws.sent if e["type"] == "complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["request_id"] == "r1"


# ------------------------------------------------------------------- cancel


@pytest.mark.asyncio
async def test_cancel_emits_cancelled_event(db_session, monkeypatch):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=_factory(db_session))
    sleep_event = asyncio.Event()

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        self.current_conversation_id = uuid4()
        if on_progress:
            await on_progress({"type": "progress", "step": "search", "status": "running"})
        sleep_event.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise ChatCancelled(
                conversation_id=str(self.current_conversation_id),
                reason="user",
            )

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "hi"})
        await sleep_event.wait()
        ws.push({"type": "cancel", "request_id": "r1"})
        await _wait_for(
            lambda: any(e["type"] == "cancelled" for e in ws.sent), timeout=2.0
        )
        ws.disconnect()

    async def with_persistence_stubbed():
        # Stub add_message so the cancelled-persistence path doesn't hit Postgres-only enum.
        import app.services.chat_ws_session as mod

        async def fake_add(*args, **kwargs):
            from unittest.mock import Mock
            return Mock()

        monkeypatch.setattr(mod.conversation_crud, "add_message", fake_add)
        await session.run()

    await asyncio.gather(with_persistence_stubbed(), driver())

    cancelled = [e for e in ws.sent if e["type"] == "cancelled"]
    assert cancelled, f"no cancelled event in {ws.sent}"
    assert cancelled[0]["request_id"] == "r1"
    assert cancelled[0]["reason"] == "user"


# ------------------------------------------------------------------ supersede


@pytest.mark.asyncio
async def test_supersede_cancels_previous_and_starts_new(db_session, monkeypatch):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=_factory(db_session))
    started_first = asyncio.Event()
    call_count = {"n": 0}

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        call_count["n"] += 1
        my_call = call_count["n"]
        self.current_conversation_id = uuid4()
        if my_call == 1:
            started_first.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise ChatCancelled(
                    conversation_id=str(self.current_conversation_id),
                    reason="superseded",
                )
        return _stub_chat_response()

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    async def with_persistence_stubbed():
        import app.services.chat_ws_session as mod

        async def fake_add(*args, **kwargs):
            from unittest.mock import Mock
            return Mock()

        monkeypatch.setattr(mod.conversation_crud, "add_message", fake_add)
        await session.run()

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "first"})
        await started_first.wait()
        ws.push({"type": "message", "request_id": "r2", "text": "second"})
        await _wait_for(
            lambda: any(
                e.get("type") == "complete" and e.get("request_id") == "r2"
                for e in ws.sent
            ),
            timeout=3.0,
        )
        ws.disconnect()

    await asyncio.gather(with_persistence_stubbed(), driver())

    triples = [(e["type"], e.get("request_id"), e.get("reason")) for e in ws.sent]
    assert ("cancelled", "r1", "superseded") in triples
    assert any(t == "complete" and rid == "r2" for t, rid, _ in triples)


# ------------------------------------------------------------- question/confirm


@pytest.mark.asyncio
async def test_confirm_resolves_question_future(db_session, monkeypatch):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=_factory(db_session))

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        self.current_conversation_id = uuid4()
        assert on_question is not None
        answer = await on_question({"prompt": "Pick 3", "choices": ["a", "b", "c"]})
        assert answer == {"picked": ["a", "b"]}
        return _stub_chat_response()

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "hi"})
        await _wait_for(
            lambda: any(e.get("type") == "question" for e in ws.sent), timeout=2.0
        )
        ws.push({
            "type": "confirm",
            "request_id": "r1",
            "answer": {"picked": ["a", "b"]},
        })
        await _wait_for(
            lambda: any(e.get("type") == "complete" for e in ws.sent), timeout=2.0
        )
        ws.disconnect()

    await asyncio.gather(session.run(), driver())

    assert any(e["type"] == "question" for e in ws.sent)
    assert any(e["type"] == "complete" for e in ws.sent)


@pytest.mark.asyncio
async def test_question_timeout_raises(db_session, monkeypatch):
    ws = FakeWebSocket()
    session = ChatWSSession(
        ws,
        db_session_factory=_factory(db_session),
        question_timeout_seconds=0.05,
    )
    timeout_seen = {"v": False}

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        self.current_conversation_id = uuid4()
        try:
            await on_question({"prompt": "hello?"})
        except QuestionTimeout:
            timeout_seen["v"] = True
            raise

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "hi"})
        await asyncio.sleep(0.3)
        ws.disconnect()

    await asyncio.gather(session.run(), driver())
    assert timeout_seen["v"]


# ----------------------------------------------------- ping/pong + disconnect


@pytest.mark.asyncio
async def test_ping_emits_pong(db_session):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=_factory(db_session))
    ws.push({"type": "auth", "token": None})
    ws.push({"type": "ping"})
    ws.disconnect()
    await session.run()
    assert any(e["type"] == "pong" for e in ws.sent)


@pytest.mark.asyncio
async def test_disconnect_mid_flight_cancels_task(db_session, monkeypatch):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=_factory(db_session))
    started = asyncio.Event()
    cancelled_seen = {"v": False}

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        self.current_conversation_id = uuid4()
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled_seen["v"] = True
            raise

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    async def with_persistence_stubbed():
        import app.services.chat_ws_session as mod

        async def fake_add(*args, **kwargs):
            from unittest.mock import Mock
            return Mock()

        monkeypatch.setattr(mod.conversation_crud, "add_message", fake_add)
        await session.run()

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "hi"})
        await started.wait()
        ws.disconnect()

    await asyncio.gather(with_persistence_stubbed(), driver())
    assert cancelled_seen["v"]
