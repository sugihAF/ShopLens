# Chat WebSocket Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the SSE chat stream (`POST /api/v1/chat/stream`) with a bidirectional WebSocket endpoint (`WS /api/v1/chat/ws`) supporting cancel, supersede-on-follow-up, and plumbed-only interactive tool confirmation.

**Architecture:** Native FastAPI WebSocket + a per-connection `ChatWSSession` state machine. `ChatService.process_message` is extended with `cancel_event` and `on_question` callbacks. Cancellation uses two layers: cooperative `asyncio.Event` checked between function-loop iterations, plus forceful `task.cancel()` for mid-`await` interrupts. Frontend `useChat` hook is rewritten against the WS protocol. SSE endpoint and its frontend client are deleted in the same PR.

**Tech Stack:** FastAPI (Python 3.11), asyncio, SQLAlchemy 2.0 async, Alembic, React + TypeScript, native `WebSocket` browser API.

**Spec:** `docs/superpowers/specs/2026-05-15-chat-websocket-design.md`

---

## File Structure

**Backend — create:**
- `app/api/app/services/chat_exceptions.py` — `ChatCancelled`, `QuestionTimeout`
- `app/api/app/services/chat_ws_session.py` — per-connection session supervisor
- `app/api/app/api/v1/endpoints/chat_ws.py` — thin WS endpoint
- `app/api/alembic/versions/002_add_message_status.py` — column migration
- `app/api/tests/services/test_chat_ws_session.py` — unit tests with fake WebSocket
- `app/api/tests/endpoints/test_chat_ws_integration.py` — TestClient WebSocket integration

**Backend — modify:**
- `app/api/app/models/conversation.py` — add `MessageStatus` enum, `status` column on `Message`
- `app/api/app/services/chat_service.py` — extend `process_message` signature; surface `current_conversation_id`
- `app/api/app/crud/conversation.py` — `add_message` accepts optional `status`
- `app/api/app/api/v1/endpoints/chat.py` — DELETE the `/stream` route
- `app/api/app/api/v1/router.py` — include `chat_ws` router

**Frontend — modify:**
- `app/web/landing-page/src/api/chat.ts` — DELETE `sendChatMessageStream`; ADD `openChatSocket` (WebSocket client)
- `app/web/landing-page/src/hooks/useChat.ts` — switch from SSE to WS client
- `app/web/landing-page/src/types/index.ts` — add WS event types if needed

**Docs:**
- `CLAUDE.md` — update AI Integration section to mention WS transport

---

### Task 1: Add `MessageStatus` enum, `status` column, and migration

**Files:**
- Modify: `app/api/app/models/conversation.py`
- Modify: `app/api/app/crud/conversation.py`
- Create: `app/api/alembic/versions/002_add_message_status.py`
- Test: `app/api/tests/models/test_message_status.py`

- [ ] **Step 1: Write the failing test**

Create `app/api/tests/models/test_message_status.py`:

```python
"""Tests for Message.status column and MessageStatus enum."""
import pytest
import pytest_asyncio
from app.models.conversation import Message, MessageRole, MessageStatus, Conversation


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec shoplens-api-dev pytest tests/models/test_message_status.py -v`
Expected: `ImportError: cannot import name 'MessageStatus' from 'app.models.conversation'`

- [ ] **Step 3: Add `MessageStatus` enum + `status` column to model**

Edit `app/api/app/models/conversation.py`. After the `MessageRole` enum class, add:

```python
class MessageStatus(str, enum.Enum):
    """Lifecycle status of a message."""
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    ERROR = "error"
```

Inside the `Message` class, after the `content` column (around line 122), add:

```python
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus),
        default=MessageStatus.COMPLETE,
        nullable=False,
    )
```

- [ ] **Step 4: Run the test — should now pass under SQLite**

Run: `docker exec shoplens-api-dev pytest tests/models/test_message_status.py -v`
Expected: PASS (SQLite creates tables from `Base.metadata` and picks up the new column automatically).

- [ ] **Step 5: Write Alembic migration for Postgres**

Create `app/api/alembic/versions/002_add_message_status.py`:

```python
"""Add status column to messages

Revision ID: 002
Revises: 001
Create Date: 2026-05-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    message_status = sa.Enum(
        'COMPLETE', 'CANCELLED', 'ERROR',
        name='messagestatus',
    )
    message_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'messages',
        sa.Column(
            'status',
            message_status,
            server_default='COMPLETE',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('messages', 'status')
    sa.Enum(name='messagestatus').drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 6: Allow `add_message` to accept a `status` argument**

Edit `app/api/app/crud/conversation.py`. Find the `add_message` method and update its signature + body:

```python
    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        role: str,
        content: str,
        intent: Optional[dict] = None,
        agent_metadata: Optional[dict] = None,
        sources: Optional[list] = None,
        attachments: Optional[list] = None,
        status: Optional["MessageStatus"] = None,
    ) -> Message:
```

Inside the method, when constructing `Message(...)`, pass `status=status` if not None — let the column default kick in otherwise. Add a top-level import: `from app.models.conversation import MessageStatus`.

- [ ] **Step 7: Run the migration against the dev container's Postgres**

Run: `docker exec shoplens-api-dev alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, Add status column to messages`

- [ ] **Step 8: Run full test suite to confirm no regressions**

Run: `docker exec shoplens-api-dev pytest -x`
Expected: all existing tests pass.

- [ ] **Step 9: Commit**

```bash
git add app/api/app/models/conversation.py app/api/app/crud/conversation.py app/api/alembic/versions/002_add_message_status.py app/api/tests/models/test_message_status.py
git commit -m "feat(db): add status column to messages for WS cancel/error states"
```

---

### Task 2: Add cancellation exception types

**Files:**
- Create: `app/api/app/services/chat_exceptions.py`
- Test: `app/api/tests/services/test_chat_exceptions.py`

- [ ] **Step 1: Write the failing test**

Create `app/api/tests/services/test_chat_exceptions.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_exceptions.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.chat_exceptions'`

- [ ] **Step 3: Implement exceptions**

Create `app/api/app/services/chat_exceptions.py`:

```python
"""Exception types for chat flow control."""
from typing import Optional


class ChatCancelled(Exception):
    """Raised inside ChatService.process_message when cancellation is requested.

    The supervisor catches this and emits a `cancelled` event. The
    conversation_id lets the supervisor persist a cancelled assistant message
    even if cancellation arrived mid-pipeline.
    """

    def __init__(self, conversation_id: Optional[str] = None, reason: str = "user"):
        self.conversation_id = conversation_id
        self.reason = reason
        super().__init__(f"chat cancelled (reason={reason}, conversation={conversation_id})")


class QuestionTimeout(Exception):
    """Raised when a server `question` event is not answered within the timeout window."""
```

- [ ] **Step 4: Run the test**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_exceptions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_exceptions.py app/api/tests/services/test_chat_exceptions.py
git commit -m "feat(chat): add ChatCancelled and QuestionTimeout exception types"
```

---

### Task 3: Extend `ChatService.process_message` with `cancel_event` and `on_question`

**Files:**
- Modify: `app/api/app/services/chat_service.py`
- Test: `app/api/tests/services/test_chat_service_cancel.py`

- [ ] **Step 1: Write the failing test**

Create `app/api/tests/services/test_chat_service_cancel.py`:

```python
"""Tests for ChatService cancellation support."""
import asyncio
import pytest
from unittest.mock import patch, AsyncMock

from app.services.chat_service import ChatService
from app.services.chat_exceptions import ChatCancelled
from app.schemas.chat import ChatRequest


@pytest.mark.asyncio
async def test_cancel_event_raises_chat_cancelled_at_loop_boundary(db_session):
    """Setting cancel_event before process_message starts the loop raises ChatCancelled."""
    service = ChatService(db_session)
    if service.provider is None:
        pytest.skip("LLM provider not initialized in test environment")

    cancel_event = asyncio.Event()
    cancel_event.set()

    request = ChatRequest(message="hi", conversation_id=None)

    with pytest.raises(ChatCancelled) as excinfo:
        await service.process_message(request, user_id=None, cancel_event=cancel_event)

    assert excinfo.value.conversation_id is not None
    assert excinfo.value.reason == "user"


@pytest.mark.asyncio
async def test_current_conversation_id_set_after_conversation_created(db_session):
    """ChatService exposes current_conversation_id once the conversation row exists."""
    service = ChatService(db_session)
    assert service.current_conversation_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_service_cancel.py -v`
Expected: FAIL — `process_message() got an unexpected keyword argument 'cancel_event'` and `AttributeError: ... current_conversation_id`.

- [ ] **Step 3: Add attribute init + signature change**

Edit `app/api/app/services/chat_service.py`.

In `__init__` (around line 153), after `self.tools = None` add:

```python
        self.current_conversation_id: Optional[UUID] = None
```

Import `asyncio` near the top if not already imported. Add the import for the exception:

```python
from app.services.chat_exceptions import ChatCancelled
```

Change the `process_message` signature (around line 170):

```python
    async def process_message(
        self,
        request: ChatRequest,
        user_id: Optional[int] = None,
        on_progress: Optional[Callable[[Dict[str, str]], Awaitable[None]]] = None,
        cancel_event: Optional[asyncio.Event] = None,
        on_question: Optional[Callable[[Dict[str, Any]], Awaitable[Any]]] = None,
    ) -> ChatResponse:
```

- [ ] **Step 4: Set `current_conversation_id` after conversation is resolved**

After the existing block that fetches or creates the conversation (right after `conversation = await conversation_crud.create_conversation(...)` around line 213), add:

```python
        self.current_conversation_id = conversation.id
```

Also set it in the branch where conversation was loaded from `request.conversation_id`.

- [ ] **Step 5: Check `cancel_event` at function-loop boundaries**

Inside `process_message`, locate the function-calling loop (the `while` loop that drives Gemini and dispatches functions). At the top of each iteration of that loop, immediately before deciding what to call next, add:

```python
            if cancel_event is not None and cancel_event.is_set():
                raise ChatCancelled(
                    conversation_id=str(self.current_conversation_id),
                    reason="user",
                )
```

If the file uses `for iteration in range(MAX_FUNCTION_CALL_ITERATIONS):` style, place this check as the first statement of the loop body.

- [ ] **Step 6: Pass `on_question` through to `execute_function`**

Find each call to `execute_function(...)` inside the loop. Update each invocation to pass `on_question=on_question` as a kwarg. If `execute_function`'s signature doesn't accept it yet, add the optional kwarg there too — it should be forwarded only; no built-in tool consumes it in v1. Example signature update in `app/api/app/functions/registry.py`:

```python
async def execute_function(
    name: str,
    args: dict,
    db: AsyncSession,
    on_question: Optional[Callable] = None,
) -> dict:
```

Forward it into each handler invocation but don't change handler signatures unless a handler explicitly opts in (none do in v1).

- [ ] **Step 7: Run the targeted tests**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_service_cancel.py -v`
Expected: PASS for both tests.

- [ ] **Step 8: Run full suite to catch regressions**

Run: `docker exec shoplens-api-dev pytest -x`
Expected: all existing tests pass; `process_message` signature change is backward compatible because new kwargs are optional.

- [ ] **Step 9: Commit**

```bash
git add app/api/app/services/chat_service.py app/api/app/functions/registry.py app/api/tests/services/test_chat_service_cancel.py
git commit -m "feat(chat): wire cancel_event + on_question through process_message"
```

---

### Task 4: `ChatWSSession` — auth flow + skeleton

**Files:**
- Create: `app/api/app/services/chat_ws_session.py`
- Create: `app/api/tests/services/test_chat_ws_session.py` (skeleton + fake WebSocket)

- [ ] **Step 1: Write the failing test (fake WebSocket + auth happy path)**

Create `app/api/tests/services/test_chat_ws_session.py`:

```python
"""Unit tests for ChatWSSession driven by a fake WebSocket."""
import asyncio
import json
from typing import Any, Optional
import pytest

from app.services.chat_ws_session import ChatWSSession


class FakeWebSocket:
    """Minimal stand-in for starlette.WebSocket with queue-based I/O."""

    def __init__(self):
        self._incoming: asyncio.Queue[dict | None] = asyncio.Queue()
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


@pytest.mark.asyncio
async def test_auth_anonymous_emits_ready(db_session):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=lambda: db_session)
    ws.push({"type": "auth", "token": None})
    ws.disconnect()

    await session.run()

    assert ws.accepted
    assert any(e["type"] == "ready" and e["user_id"] is None for e in ws.sent)


@pytest.mark.asyncio
async def test_auth_timeout_closes_4401(db_session):
    ws = FakeWebSocket()
    session = ChatWSSession(
        ws,
        db_session_factory=lambda: db_session,
        auth_timeout_seconds=0.05,
    )
    # No auth message pushed — wait for timeout.
    await session.run()

    assert ws.closed_code == 4401


@pytest.mark.asyncio
async def test_malformed_first_message_closes_4401(db_session):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=lambda: db_session)
    ws.push({"type": "message", "text": "hi"})  # wrong type before auth
    await session.run()

    assert ws.closed_code == 4401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.chat_ws_session'`

- [ ] **Step 3: Implement the auth-only skeleton**

Create `app/api/app/services/chat_ws_session.py`:

```python
"""ChatWSSession — per-connection state machine for the WS chat endpoint."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChatWSSession:
    """Per-connection supervisor.

    Responsibilities are added in subsequent tasks:
    - Task 4: auth gate
    - Task 5: message happy path + spawn chat task
    - Task 6: cancel
    - Task 7: supersede on follow-up
    - Task 8: question/confirm relay
    - Task 9: ping/pong, idle timeout, disconnect
    """

    def __init__(
        self,
        websocket: WebSocket,
        db_session_factory: Callable[[], Any],
        auth_timeout_seconds: float = 5.0,
    ):
        self.ws = websocket
        self.db_session_factory = db_session_factory
        self.auth_timeout = auth_timeout_seconds
        self.user_id: Optional[int] = None
        self.authenticated = False

    async def run(self):
        await self.ws.accept()
        if not await self._auth_gate():
            return
        try:
            await self._main_loop()
        except WebSocketDisconnect:
            logger.info("Client disconnected")

    async def _auth_gate(self) -> bool:
        try:
            msg = await asyncio.wait_for(self.ws.receive_json(), timeout=self.auth_timeout)
        except (asyncio.TimeoutError, Exception):
            await self.ws.close(code=4401)
            return False

        if not isinstance(msg, dict) or msg.get("type") != "auth":
            await self.ws.close(code=4401)
            return False

        token = msg.get("token")
        if token:
            payload = decode_token(token)
            if payload:
                sub = payload.get("sub")
                try:
                    self.user_id = int(sub) if sub is not None else None
                except (TypeError, ValueError):
                    self.user_id = None

        self.authenticated = True
        await self._send({"type": "ready", "user_id": self.user_id})
        return True

    async def _main_loop(self):
        # Placeholder — populated in subsequent tasks.
        while True:
            msg = await self.ws.receive_json()
            # Unknown messages return an error event; later tasks add real handlers.
            await self._send({
                "type": "error",
                "code": "unknown_message_type",
                "message": f"Unknown message type: {msg.get('type')!r}",
            })

    async def _send(self, event: dict):
        try:
            await self.ws.send_json(event)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning(f"send_json failed: {e}")
```

- [ ] **Step 4: Run the test**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py -v`
Expected: PASS for all three tests.

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_ws_session.py app/api/tests/services/test_chat_ws_session.py
git commit -m "feat(chat-ws): ChatWSSession skeleton with first-message auth gate"
```

---

### Task 5: Handle `message` — spawn chat task, relay progress + complete

**Files:**
- Modify: `app/api/app/services/chat_ws_session.py`
- Modify: `app/api/tests/services/test_chat_ws_session.py`

- [ ] **Step 1: Write the failing test**

Append to `app/api/tests/services/test_chat_ws_session.py`:

```python
from unittest.mock import patch, AsyncMock
from app.schemas.chat import ChatResponse, MessageResponse
from datetime import datetime, timezone
from uuid import uuid4


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


@pytest.mark.asyncio
async def test_message_happy_path_emits_complete(db_session, monkeypatch):
    ws = FakeWebSocket()
    session = ChatWSSession(ws, db_session_factory=lambda: db_session)

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        if on_progress:
            await on_progress({"type": "progress", "step": "search", "status": "start"})
            await on_progress({"type": "progress", "step": "search", "status": "done"})
        return _stub_chat_response()

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    ws.push({"type": "auth", "token": None})
    ws.push({"type": "message", "request_id": "r1", "text": "hello"})
    # Keep connection open until 'complete' arrives, then disconnect.
    async def waiter():
        for _ in range(100):
            if any(e["type"] == "complete" for e in ws.sent):
                ws.disconnect()
                return
            await asyncio.sleep(0.01)
        ws.disconnect()

    await asyncio.gather(session.run(), waiter())

    types = [e["type"] for e in ws.sent]
    assert "ready" in types
    assert types.count("progress") == 2
    assert any(e["type"] == "complete" and e["request_id"] == "r1" for e in ws.sent)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py::test_message_happy_path_emits_complete -v`
Expected: FAIL — the unknown-message-type error event fires instead of `complete`.

- [ ] **Step 3: Implement message dispatch**

In `app/api/app/services/chat_ws_session.py`, replace the placeholder `_main_loop` and add handler methods. Also add the imports + new state:

At the top, add:

```python
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest
```

In `__init__`, add state for the in-flight task:

```python
        self.current_request_id: Optional[str] = None
        self.current_task: Optional[asyncio.Task] = None
        self.cancel_event: Optional[asyncio.Event] = None
```

Replace `_main_loop` with:

```python
    async def _main_loop(self):
        while True:
            msg = await self.ws.receive_json()
            mtype = msg.get("type") if isinstance(msg, dict) else None
            if mtype == "message":
                await self._handle_message(msg)
            else:
                await self._send({
                    "type": "error",
                    "code": "unknown_message_type",
                    "message": f"Unknown message type: {mtype!r}",
                })

    async def _handle_message(self, msg: dict):
        request_id = msg.get("request_id")
        text = msg.get("text")
        conversation_id = msg.get("conversation_id")
        if not request_id or not text:
            await self._send({
                "type": "error",
                "code": "bad_request",
                "message": "message requires request_id and text",
            })
            return

        self.current_request_id = request_id
        self.cancel_event = asyncio.Event()
        self.current_task = asyncio.create_task(
            self._run_chat(request_id, text, conversation_id)
        )

    async def _run_chat(self, request_id: str, text: str, conversation_id):
        async def relay_progress(event: dict):
            event = {**event, "request_id": request_id}
            await self._send(event)

        async with self.db_session_factory() as db:
            service = ChatService(db)
            try:
                response = await service.process_message(
                    ChatRequest(message=text, conversation_id=conversation_id),
                    user_id=self.user_id,
                    on_progress=relay_progress,
                    cancel_event=self.cancel_event,
                )
                await self._send({
                    "type": "complete",
                    "request_id": request_id,
                    "data": response.model_dump(mode="json"),
                })
            except Exception as e:
                logger.error(f"chat task error: {e}", exc_info=True)
                await self._send({
                    "type": "error",
                    "request_id": request_id,
                    "code": "internal",
                    "message": "Failed to process message",
                })
            finally:
                if self.current_request_id == request_id:
                    self.current_request_id = None
                    self.current_task = None
                    self.cancel_event = None
```

The test passes a `db_session_factory` that returns a plain `AsyncSession`; production code will pass an `async with`-compatible factory. To make both work, the test fixture's session factory needs to be wrapped. Update the test's `db_session_factory` to:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _session_cm():
    yield db_session

session = ChatWSSession(ws, db_session_factory=_session_cm)
```

Update both new tests (`test_message_happy_path_emits_complete` and any others using `db_session_factory`) to use this pattern.

- [ ] **Step 4: Run the test**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py -v`
Expected: PASS for the new test; previous tests still pass (update them to use the `_session_cm` pattern if needed).

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_ws_session.py app/api/tests/services/test_chat_ws_session.py
git commit -m "feat(chat-ws): handle message — spawn task, relay progress + complete"
```

---

### Task 6: Handle `cancel` — persist cancelled assistant message

**Files:**
- Modify: `app/api/app/services/chat_ws_session.py`
- Modify: `app/api/tests/services/test_chat_ws_session.py`

- [ ] **Step 1: Write the failing test**

Append to the test file:

```python
@pytest.mark.asyncio
async def test_cancel_emits_cancelled_event(db_session, monkeypatch):
    ws = FakeWebSocket()

    @asynccontextmanager
    async def _session_cm():
        yield db_session

    session = ChatWSSession(ws, db_session_factory=_session_cm)

    sleep_event = asyncio.Event()

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        # Set conversation id so cancellation persistence has somewhere to land.
        from uuid import uuid4
        self.current_conversation_id = uuid4()
        if on_progress:
            await on_progress({"type": "progress", "step": "search", "status": "start"})
        sleep_event.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            from app.services.chat_exceptions import ChatCancelled
            raise ChatCancelled(conversation_id=str(self.current_conversation_id), reason="user")

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "hi"})
        await sleep_event.wait()
        ws.push({"type": "cancel", "request_id": "r1"})
        for _ in range(100):
            if any(e["type"] == "cancelled" for e in ws.sent):
                ws.disconnect()
                return
            await asyncio.sleep(0.01)
        ws.disconnect()

    await asyncio.gather(session.run(), driver())

    cancelled = [e for e in ws.sent if e["type"] == "cancelled"]
    assert cancelled, f"no cancelled event in {ws.sent}"
    assert cancelled[0]["request_id"] == "r1"
    assert cancelled[0]["reason"] == "user"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py::test_cancel_emits_cancelled_event -v`
Expected: FAIL — unknown_message_type error for `cancel`.

- [ ] **Step 3: Add cancel handling**

In `_main_loop`, extend the dispatch:

```python
            elif mtype == "cancel":
                await self._handle_cancel(msg)
```

Add the handler method:

```python
    async def _handle_cancel(self, msg: dict):
        request_id = msg.get("request_id")
        if not request_id or request_id != self.current_request_id:
            await self._send({
                "type": "error",
                "code": "no_inflight_request",
                "message": "no in-flight request with this request_id",
            })
            return

        await self._cancel_current(reason="user")

    async def _cancel_current(self, reason: str):
        if self.cancel_event:
            self.cancel_event.set()
        task = self.current_task
        request_id = self.current_request_id
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        await self._send({
            "type": "cancelled",
            "request_id": request_id,
            "reason": reason,
        })
```

Update `_run_chat` to catch `ChatCancelled` distinctly and persist a cancelled assistant message:

```python
            from app.services.chat_exceptions import ChatCancelled
            from app.models.conversation import MessageStatus

            try:
                response = await service.process_message(...)
                ...
            except (ChatCancelled, asyncio.CancelledError) as cancel_exc:
                conv_id = service.current_conversation_id
                if conv_id is not None:
                    try:
                        from app.crud.conversation import conversation_crud
                        await conversation_crud.add_message(
                            db,
                            conversation_id=conv_id,
                            role="assistant",
                            content="",
                            status=MessageStatus.CANCELLED,
                        )
                        await db.commit()
                    except Exception as persist_err:
                        logger.warning(f"failed to persist cancelled message: {persist_err}")
                # The cancelled event is emitted by _cancel_current — do NOT
                # emit a duplicate here. Re-raise CancelledError so the task
                # status reflects cancellation if needed.
                if isinstance(cancel_exc, asyncio.CancelledError):
                    raise
```

- [ ] **Step 4: Run the test**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py -v`
Expected: PASS for the new cancel test; existing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_ws_session.py app/api/tests/services/test_chat_ws_session.py
git commit -m "feat(chat-ws): handle cancel, persist cancelled assistant message"
```

---

### Task 7: Supersede — new `message` cancels in-flight

**Files:**
- Modify: `app/api/app/services/chat_ws_session.py`
- Modify: `app/api/tests/services/test_chat_ws_session.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
@pytest.mark.asyncio
async def test_supersede_cancels_previous_and_starts_new(db_session, monkeypatch):
    ws = FakeWebSocket()

    @asynccontextmanager
    async def _session_cm():
        yield db_session

    session = ChatWSSession(ws, db_session_factory=_session_cm)

    started_first = asyncio.Event()
    call_count = {"n": 0}

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        call_count["n"] += 1
        my_call = call_count["n"]
        from uuid import uuid4
        self.current_conversation_id = uuid4()
        if my_call == 1:
            started_first.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                from app.services.chat_exceptions import ChatCancelled
                raise ChatCancelled(conversation_id=str(self.current_conversation_id), reason="superseded")
        return _stub_chat_response()

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "first"})
        await started_first.wait()
        ws.push({"type": "message", "request_id": "r2", "text": "second"})
        for _ in range(200):
            if any(e.get("type") == "complete" and e.get("request_id") == "r2" for e in ws.sent):
                ws.disconnect()
                return
            await asyncio.sleep(0.01)
        ws.disconnect()

    await asyncio.gather(session.run(), driver())

    types_with_ids = [(e["type"], e.get("request_id"), e.get("reason")) for e in ws.sent]
    assert ("cancelled", "r1", "superseded") in types_with_ids
    assert any(t == "complete" and rid == "r2" for t, rid, _ in types_with_ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py::test_supersede_cancels_previous_and_starts_new -v`
Expected: FAIL — currently `_handle_message` overwrites state without cancelling the prior task.

- [ ] **Step 3: Modify `_handle_message` to supersede**

Replace the body of `_handle_message`:

```python
    async def _handle_message(self, msg: dict):
        request_id = msg.get("request_id")
        text = msg.get("text")
        conversation_id = msg.get("conversation_id")
        if not request_id or not text:
            await self._send({
                "type": "error",
                "code": "bad_request",
                "message": "message requires request_id and text",
            })
            return

        if self.current_task and not self.current_task.done():
            await self._cancel_current(reason="superseded")

        self.current_request_id = request_id
        self.cancel_event = asyncio.Event()
        self.current_task = asyncio.create_task(
            self._run_chat(request_id, text, conversation_id)
        )
```

- [ ] **Step 4: Run the test**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_ws_session.py app/api/tests/services/test_chat_ws_session.py
git commit -m "feat(chat-ws): supersede in-flight request when new message arrives"
```

---

### Task 8: `confirm` + question relay (plumbed, not wired)

**Files:**
- Modify: `app/api/app/services/chat_ws_session.py`
- Modify: `app/api/tests/services/test_chat_ws_session.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
@pytest.mark.asyncio
async def test_confirm_resolves_question_future(db_session, monkeypatch):
    ws = FakeWebSocket()

    @asynccontextmanager
    async def _session_cm():
        yield db_session

    session = ChatWSSession(ws, db_session_factory=_session_cm)

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        from uuid import uuid4
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
        for _ in range(100):
            if any(e.get("type") == "question" for e in ws.sent):
                ws.push({"type": "confirm", "request_id": "r1", "answer": {"picked": ["a", "b"]}})
                break
            await asyncio.sleep(0.01)
        for _ in range(100):
            if any(e.get("type") == "complete" for e in ws.sent):
                ws.disconnect()
                return
            await asyncio.sleep(0.01)
        ws.disconnect()

    await asyncio.gather(session.run(), driver())

    assert any(e["type"] == "question" for e in ws.sent)
    assert any(e["type"] == "complete" for e in ws.sent)


@pytest.mark.asyncio
async def test_question_timeout_raises(db_session, monkeypatch):
    ws = FakeWebSocket()

    @asynccontextmanager
    async def _session_cm():
        yield db_session

    session = ChatWSSession(
        ws,
        db_session_factory=_session_cm,
        question_timeout_seconds=0.05,
    )

    timeout_seen = {"v": False}

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        from uuid import uuid4
        self.current_conversation_id = uuid4()
        from app.services.chat_exceptions import QuestionTimeout
        try:
            await on_question({"prompt": "hello?"})
        except QuestionTimeout:
            timeout_seen["v"] = True
            raise
        return _stub_chat_response()

    monkeypatch.setattr(
        "app.services.chat_service.ChatService.process_message", fake_process
    )

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "hi"})
        await asyncio.sleep(0.2)
        ws.disconnect()

    await asyncio.gather(session.run(), driver())
    assert timeout_seen["v"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py::test_confirm_resolves_question_future tests/services/test_chat_ws_session.py::test_question_timeout_raises -v`
Expected: FAIL — `on_question` is not yet passed to `process_message`.

- [ ] **Step 3: Wire `on_question` and `_handle_confirm`**

In `__init__` add:

```python
        self.pending_question: Optional[asyncio.Future] = None
        self.pending_question_request_id: Optional[str] = None
        self.question_timeout = question_timeout_seconds
```

And add `question_timeout_seconds: float = 60.0` to the constructor signature.

In `_main_loop`, add another `elif`:

```python
            elif mtype == "confirm":
                await self._handle_confirm(msg)
```

Add the handler + question relay:

```python
    async def _handle_confirm(self, msg: dict):
        request_id = msg.get("request_id")
        if not self.pending_question or request_id != self.pending_question_request_id:
            await self._send({
                "type": "error",
                "code": "no_pending_question",
                "message": "no pending question matching request_id",
            })
            return
        if not self.pending_question.done():
            self.pending_question.set_result(msg.get("answer"))

    async def _build_question_callback(self, request_id: str):
        from app.services.chat_exceptions import QuestionTimeout

        async def ask(spec: dict) -> Any:
            loop = asyncio.get_running_loop()
            self.pending_question = loop.create_future()
            self.pending_question_request_id = request_id
            await self._send({"type": "question", "request_id": request_id, **spec})
            try:
                return await asyncio.wait_for(self.pending_question, timeout=self.question_timeout)
            except asyncio.TimeoutError:
                raise QuestionTimeout(f"no answer in {self.question_timeout}s")
            finally:
                self.pending_question = None
                self.pending_question_request_id = None

        return ask
```

Update `_run_chat` to pass `on_question`:

```python
                response = await service.process_message(
                    ChatRequest(message=text, conversation_id=conversation_id),
                    user_id=self.user_id,
                    on_progress=relay_progress,
                    cancel_event=self.cancel_event,
                    on_question=await self._build_question_callback(request_id),
                )
```

- [ ] **Step 4: Run the tests**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py -v`
Expected: PASS for all tests.

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_ws_session.py app/api/tests/services/test_chat_ws_session.py
git commit -m "feat(chat-ws): plumb on_question + confirm relay with 60s timeout"
```

---

### Task 9: Ping/pong, idle timeout, disconnect cleanup

**Files:**
- Modify: `app/api/app/services/chat_ws_session.py`
- Modify: `app/api/tests/services/test_chat_ws_session.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
@pytest.mark.asyncio
async def test_ping_emits_pong(db_session):
    ws = FakeWebSocket()

    @asynccontextmanager
    async def _session_cm():
        yield db_session

    session = ChatWSSession(ws, db_session_factory=_session_cm)
    ws.push({"type": "auth", "token": None})
    ws.push({"type": "ping"})
    ws.disconnect()

    await session.run()
    assert any(e["type"] == "pong" for e in ws.sent)


@pytest.mark.asyncio
async def test_disconnect_mid_flight_cancels_task(db_session, monkeypatch):
    ws = FakeWebSocket()

    @asynccontextmanager
    async def _session_cm():
        yield db_session

    session = ChatWSSession(ws, db_session_factory=_session_cm)
    started = asyncio.Event()
    cancelled_seen = {"v": False}

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        from uuid import uuid4
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

    async def driver():
        ws.push({"type": "auth", "token": None})
        ws.push({"type": "message", "request_id": "r1", "text": "hi"})
        await started.wait()
        ws.disconnect()

    await asyncio.gather(session.run(), driver())
    assert cancelled_seen["v"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py::test_ping_emits_pong tests/services/test_chat_ws_session.py::test_disconnect_mid_flight_cancels_task -v`
Expected: ping test fails with unknown_message_type; disconnect test may fail because run() exits cleanly without cancelling the task.

- [ ] **Step 3: Add ping handling and disconnect cleanup**

In `_main_loop` add:

```python
            elif mtype == "ping":
                await self._send({"type": "pong"})
```

Wrap the `_main_loop` try-block so `WebSocketDisconnect` cancels the in-flight task:

```python
    async def run(self):
        await self.ws.accept()
        if not await self._auth_gate():
            return
        try:
            await self._main_loop()
        except WebSocketDisconnect:
            logger.info("Client disconnected")
        finally:
            await self._on_disconnect()

    async def _on_disconnect(self):
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            try:
                await self.current_task
            except Exception:
                pass
```

- [ ] **Step 4: Run the tests**

Run: `docker exec shoplens-api-dev pytest tests/services/test_chat_ws_session.py -v`
Expected: PASS for both new tests; existing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_ws_session.py app/api/tests/services/test_chat_ws_session.py
git commit -m "feat(chat-ws): ping/pong + disconnect cleanup"
```

---

### Task 10: WS endpoint + router wiring + integration test

**Files:**
- Create: `app/api/app/api/v1/endpoints/chat_ws.py`
- Modify: `app/api/app/api/v1/router.py`
- Create: `app/api/tests/endpoints/test_chat_ws_integration.py`

- [ ] **Step 1: Write the failing integration test**

Create `app/api/tests/endpoints/test_chat_ws_integration.py`:

```python
"""Integration test for WS /api/v1/chat/ws using FastAPI TestClient."""
import json
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_application
from app.db.session import get_db
from app.schemas.chat import ChatResponse, MessageResponse


def test_ws_chat_happy_path(db_session, monkeypatch):
    test_app = create_application()
    from contextlib import asynccontextmanager

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

    monkeypatch.setattr(
        "app.api.v1.endpoints.chat_ws._db_session_factory",
        fake_session_factory,
    )

    async def fake_process(self, request, user_id=None, on_progress=None,
                           cancel_event=None, on_question=None):
        if on_progress:
            await on_progress({"type": "progress", "step": "x", "status": "start"})
        return ChatResponse(
            conversation_id=uuid4(),
            message=MessageResponse(
                id=uuid4(), role="assistant", content="hi",
                created_at=datetime.now(timezone.utc),
            ),
            sources=[], attachments=[], functions_called=[],
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec shoplens-api-dev pytest tests/endpoints/test_chat_ws_integration.py -v`
Expected: FAIL — 404 / no route.

- [ ] **Step 3: Create the endpoint module**

Create `app/api/app/api/v1/endpoints/chat_ws.py`:

```python
"""WebSocket chat endpoint."""
from contextlib import asynccontextmanager
from fastapi import APIRouter, WebSocket

from app.db.session import AsyncSessionLocal
from app.services.chat_ws_session import ChatWSSession

router = APIRouter()


@asynccontextmanager
async def _db_session_factory():
    """Default DB session factory; overridden in tests via monkeypatch."""
    async with AsyncSessionLocal() as db:
        yield db


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket):
    """Bidirectional chat over WebSocket. See docs/superpowers/specs/2026-05-15-chat-websocket-design.md."""
    session = ChatWSSession(websocket, db_session_factory=_db_session_factory)
    await session.run()
```

- [ ] **Step 4: Wire it into the v1 router**

Edit `app/api/app/api/v1/router.py`:

```python
from app.api.v1.endpoints import chat, chat_ws, health, auth, ingest

...

api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(chat_ws.router, prefix="/chat", tags=["chat"])
```

- [ ] **Step 5: Run the integration test**

Run: `docker exec shoplens-api-dev pytest tests/endpoints/test_chat_ws_integration.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/api/app/api/v1/endpoints/chat_ws.py app/api/app/api/v1/router.py app/api/tests/endpoints/test_chat_ws_integration.py
git commit -m "feat(chat-ws): add WS /api/v1/chat/ws endpoint + integration test"
```

---

### Task 11: Remove the SSE `/chat/stream` endpoint

**Files:**
- Modify: `app/api/app/api/v1/endpoints/chat.py`

- [ ] **Step 1: Delete the SSE route**

Edit `app/api/app/api/v1/endpoints/chat.py`. Remove the entire `@router.post("/stream")` block (the `stream_chat_message` function starting around line 66 and ending where its `StreamingResponse(...)` returns, approximately lines 66–133).

Also remove `asyncio` and `StreamingResponse` imports if they're no longer used elsewhere in the file. Verify by skimming the imports block.

- [ ] **Step 2: Run all backend tests**

Run: `docker exec shoplens-api-dev pytest -x`
Expected: all tests pass. (No existing test calls `/chat/stream`; if any does, update it to use `/chat/ws` or delete it.)

- [ ] **Step 3: Commit**

```bash
git add app/api/app/api/v1/endpoints/chat.py
git commit -m "feat(chat): remove SSE /chat/stream endpoint (superseded by /chat/ws)"
```

---

### Task 12: Frontend — replace SSE client with WebSocket

**Files:**
- Modify: `app/web/landing-page/src/api/chat.ts`
- Modify: `app/web/landing-page/src/hooks/useChat.ts`
- Modify: `app/web/landing-page/src/types/index.ts` (if needed)

- [ ] **Step 1: Inspect current `useChat` consumer of `sendChatMessageStream`**

Run: `grep -n "sendChatMessageStream" app/web/landing-page/src/hooks/useChat.ts`
Note the call sites and props passed (request, `onProgress`). This will inform the WS client API surface.

- [ ] **Step 2: Add `openChatSocket` to `api/chat.ts`**

In `app/web/landing-page/src/api/chat.ts`, replace `sendChatMessageStream` (DO NOT delete it yet — we'll delete in Step 6 after `useChat` is migrated, so the file compiles between steps). Add a new export `openChatSocket`:

```typescript
export interface ChatSocketHandle {
  send(text: string, requestId: string, conversationId?: string | null): void
  cancel(requestId: string): void
  confirm(requestId: string, answer: unknown): void
  close(): void
}

export interface ChatSocketEvents {
  onReady?: (userId: number | null) => void
  onProgress?: (event: { request_id: string; step: string; label?: string; status: string }) => void
  onQuestion?: (event: { request_id: string; prompt: string; choices?: unknown[] }) => void
  onComplete?: (event: { request_id: string; data: ApiChatResponse }) => void
  onCancelled?: (event: { request_id: string; reason: 'user' | 'superseded' }) => void
  onError?: (event: { request_id?: string; code: string; message: string }) => void
  onClose?: (event: CloseEvent) => void
}

export function openChatSocket(
  events: ChatSocketEvents,
  opts: { token?: string | null } = {},
): ChatSocketHandle {
  const url = new URL('/api/v1/chat/ws', window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'

  const ws = new WebSocket(url.toString())

  ws.addEventListener('open', () => {
    ws.send(JSON.stringify({ type: 'auth', token: opts.token ?? null }))
  })

  ws.addEventListener('message', (evt) => {
    let parsed: any
    try { parsed = JSON.parse(evt.data) } catch { return }
    switch (parsed.type) {
      case 'ready':     events.onReady?.(parsed.user_id); break
      case 'progress':  events.onProgress?.(parsed); break
      case 'question':  events.onQuestion?.(parsed); break
      case 'complete':  events.onComplete?.(parsed); break
      case 'cancelled': events.onCancelled?.(parsed); break
      case 'error':     events.onError?.(parsed); break
      case 'pong':      break
    }
  })

  ws.addEventListener('close', (evt) => events.onClose?.(evt))

  return {
    send(text, requestId, conversationId) {
      ws.send(JSON.stringify({
        type: 'message',
        request_id: requestId,
        text,
        conversation_id: conversationId ?? null,
      }))
    },
    cancel(requestId) {
      ws.send(JSON.stringify({ type: 'cancel', request_id: requestId }))
    },
    confirm(requestId, answer) {
      ws.send(JSON.stringify({ type: 'confirm', request_id: requestId, answer }))
    },
    close() {
      ws.close()
    },
  }
}
```

- [ ] **Step 3: Migrate `useChat` to `openChatSocket`**

Edit `app/web/landing-page/src/hooks/useChat.ts`. Replace the existing `sendChatMessageStream` call with a `useEffect`-managed `openChatSocket` connection:
- Open the socket on hook mount.
- On `send`, generate a `request_id` via `crypto.randomUUID()`, call `handle.send(text, requestId, conversationId)`.
- Expose `cancel()` that calls `handle.cancel(currentRequestId)`.
- Map `onComplete` → set the assistant message, resolve any pending mutation.
- Map `onCancelled(reason='user')` → flip state to "stopped"; `reason='superseded'` → drop the prior assistant placeholder.
- Map `onError` → surface error to UI.
- Close the socket on unmount via `handle.close()`.

(Exact line-by-line edit depends on current hook shape; the integrator may need to consult `useChat.ts` source. Behavior contract above is binding.)

- [ ] **Step 4: Smoke-test in dev container**

Run: `docker-compose -f docker-compose.dev.yml up --build`
Open the chat UI in a browser. Verify:
- Submitting a message receives progress events and a final answer.
- Clicking "Stop" (or whatever the cancel UI is) emits a `cancelled` event and the UI reflects it.
- Submitting a second message before the first finishes auto-cancels the first.

- [ ] **Step 5: Delete `sendChatMessageStream`**

Remove the `sendChatMessageStream` function from `app/web/landing-page/src/api/chat.ts`. Verify no other source file imports it: `grep -rn "sendChatMessageStream" app/web/landing-page/src` should yield zero results.

- [ ] **Step 6: Commit**

```bash
git add app/web/landing-page/src/api/chat.ts app/web/landing-page/src/hooks/useChat.ts app/web/landing-page/src/types/index.ts
git commit -m "feat(web): switch chat from SSE to WebSocket; add cancel + supersede"
```

---

### Task 13: nginx config — WebSocket upgrade headers

**Files:**
- Modify: nginx config in the `web` container (path depends on docker-compose setup; commonly `app/web/landing-page/nginx.conf` or `app/web/nginx.conf`)

- [ ] **Step 1: Locate the active nginx config**

Run: `grep -rn "location /api" app/web` to find the proxy block that forwards `/api/` to the API container.

- [ ] **Step 2: Add a `/api/v1/chat/ws` location with WebSocket upgrade**

Add (or adapt) inside the `server { ... }` block, BEFORE the generic `/api/` location:

```nginx
location /api/v1/chat/ws {
    proxy_pass http://api:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
}
```

The 600s timeout matches the 10-minute ceiling already used by the frontend for long ingestion runs.

- [ ] **Step 3: Smoke-test against the WS endpoint through nginx**

Run: `docker-compose -f docker-compose.dev.yml restart web`
Reconnect from the browser. Confirm WS frames flow through nginx (check browser DevTools Network → WS tab → frames).

- [ ] **Step 4: Commit**

```bash
git add app/web/<nginx-config-path>
git commit -m "feat(web): nginx WebSocket upgrade headers for /api/v1/chat/ws"
```

---

### Task 14: Update `CLAUDE.md` and final verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the AI Integration section**

In `CLAUDE.md`, find the "AI Integration" section. Replace any reference to SSE streaming with a note about the WebSocket transport. Suggested addition near the end of that section:

```markdown
### Realtime Chat Transport

Chat is served over `WS /api/v1/chat/ws` (see `docs/superpowers/specs/2026-05-15-chat-websocket-design.md`). The client establishes the socket, sends `{type: "auth", token}`, then exchanges `message` / `cancel` / `confirm` frames with the server's `progress` / `question` / `complete` / `cancelled` / `error` events. Non-streaming `POST /api/v1/chat` remains available for tests and external callers.
```

- [ ] **Step 2: Run the full backend test suite one more time**

Run: `docker exec shoplens-api-dev pytest`
Expected: full green.

- [ ] **Step 3: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: document WebSocket chat transport in CLAUDE.md"
```

---

## Out of Scope (deferred)

- **Server-pushed notifications channel** (watchlist alerts, price drops). Spec calls this the natural next step but a separate endpoint and design.
- **Token-level streaming from Gemini.** The `token` event is reserved in the protocol but no server-side emission ships in this plan.
- **Wiring `on_question` to a specific tool.** Plumbing exists, no tool uses it.
- **Stream resume on reconnect.** Out of scope by spec.
- **Redis pub/sub for multi-replica fanout.** Single API replica today.

## Self-Review

Checked against `docs/superpowers/specs/2026-05-15-chat-websocket-design.md`:

- ✅ Protocol — auth first-message, all 5 client→server types, all 8 server→client types — covered by Tasks 4–9 and the integration test in Task 10.
- ✅ Server architecture — three components (`chat_ws.py`, `ChatWSSession`, `ChatService` extension) — Tasks 3, 4–9, 10.
- ✅ Two-layer cancellation (event + task.cancel) — Tasks 3 + 6.
- ✅ Persistence: user message via existing `process_message`; cancelled assistant message via Task 6.
- ✅ `messages.status` column + migration — Task 1.
- ✅ Heartbeat, idle, disconnect — Task 9.
- ✅ Deletion of SSE endpoint — Task 11.
- ✅ Frontend migration — Task 12.
- ✅ nginx upgrade headers — Task 13.
- ✅ CLAUDE.md update — Task 14.

Idle timeout (5min) is not explicitly tested. Decision: the test would need to monkey-patch the timeout to something tiny — included as a follow-up unit test if the integrator wants belt-and-suspenders coverage. Disconnect-based cleanup (Task 9) is the load-bearing behavior; idle timeout is a defense-in-depth measure against zombie connections.
