"""ChatWSSession — per-connection state machine for the WS chat endpoint.

See `docs/superpowers/specs/2026-05-15-chat-websocket-design.md` for the protocol.
"""
from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Any, Awaitable, Callable, Optional

from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.security import decode_token
from app.models.conversation import MessageStatus
from app.schemas.chat import ChatRequest
from app.services.chat_exceptions import ChatCancelled, QuestionTimeout
from app.services.chat_service import ChatService
from app.crud.conversation import conversation_crud

logger = get_logger(__name__)


SessionFactory = Callable[[], AbstractAsyncContextManager]


class ChatWSSession:
    """Per-connection supervisor for the chat WebSocket endpoint."""

    def __init__(
        self,
        websocket: WebSocket,
        db_session_factory: SessionFactory,
        auth_timeout_seconds: float = 5.0,
        question_timeout_seconds: float = 60.0,
    ):
        self.ws = websocket
        self.db_session_factory = db_session_factory
        self.auth_timeout = auth_timeout_seconds
        self.question_timeout = question_timeout_seconds

        self.user_id: Optional[int] = None
        self.authenticated = False

        self.current_request_id: Optional[str] = None
        self.current_task: Optional[asyncio.Task] = None
        self.cancel_event: Optional[asyncio.Event] = None

        self.pending_question: Optional[asyncio.Future] = None
        self.pending_question_request_id: Optional[str] = None

    async def run(self):
        await self.ws.accept()
        if not await self._auth_gate():
            return
        try:
            await self._main_loop()
        except WebSocketDisconnect:
            logger.info("chat-ws: client disconnected")
        finally:
            await self._on_disconnect()

    # ------------------------------------------------------------------ auth

    async def _auth_gate(self) -> bool:
        try:
            msg = await asyncio.wait_for(
                self.ws.receive_json(), timeout=self.auth_timeout
            )
        except (asyncio.TimeoutError, Exception):
            await self._safe_close(code=4401)
            return False

        if not isinstance(msg, dict) or msg.get("type") != "auth":
            await self._safe_close(code=4401)
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

    # ------------------------------------------------------------- main loop

    async def _main_loop(self):
        while True:
            msg = await self.ws.receive_json()
            mtype = msg.get("type") if isinstance(msg, dict) else None
            if mtype == "message":
                await self._handle_message(msg)
            elif mtype == "cancel":
                await self._handle_cancel(msg)
            elif mtype == "confirm":
                await self._handle_confirm(msg)
            elif mtype == "ping":
                await self._send({"type": "pong"})
            else:
                await self._send({
                    "type": "error",
                    "code": "unknown_message_type",
                    "message": f"Unknown message type: {mtype!r}",
                })

    # -------------------------------------------------------- message handler

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

        # Supersede any in-flight request on this connection.
        if self.current_task and not self.current_task.done():
            await self._cancel_current(reason="superseded")

        self.current_request_id = request_id
        self.cancel_event = asyncio.Event()
        self.current_task = asyncio.create_task(
            self._run_chat(request_id, text, conversation_id)
        )

    async def _run_chat(self, request_id: str, text: str, conversation_id):
        async def relay_progress(event: dict):
            await self._send({**event, "request_id": request_id})

        on_question = await self._build_question_callback(request_id)

        async with self.db_session_factory() as db:
            service = ChatService(db)
            try:
                response = await service.process_message(
                    ChatRequest(message=text, conversation_id=conversation_id),
                    user_id=self.user_id,
                    on_progress=relay_progress,
                    cancel_event=self.cancel_event,
                    on_question=on_question,
                )
                await self._send({
                    "type": "complete",
                    "request_id": request_id,
                    "data": response.model_dump(mode="json"),
                })
            except (ChatCancelled, asyncio.CancelledError) as cancel_exc:
                # Persist a cancelled assistant message so the conversation
                # history records the interrupted turn.
                conv_id = service.current_conversation_id
                if conv_id is not None:
                    try:
                        await conversation_crud.add_message(
                            db,
                            conversation_id=conv_id,
                            role="assistant",
                            content="",
                            status=MessageStatus.CANCELLED,
                        )
                        await db.commit()
                    except Exception as persist_err:
                        logger.warning(
                            f"chat-ws: failed to persist cancelled message: {persist_err}"
                        )
                # The `cancelled` event is emitted by _cancel_current. Re-raise
                # CancelledError so the asyncio.Task status reflects cancellation.
                if isinstance(cancel_exc, asyncio.CancelledError):
                    raise
            except Exception as e:
                logger.error(f"chat-ws: chat task error: {e}", exc_info=True)
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

    # --------------------------------------------------------- cancel handler

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
        request_id = self.current_request_id
        if self.cancel_event:
            self.cancel_event.set()
        task = self.current_task
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

    # ----------------------------------------------------- question / confirm

    async def _handle_confirm(self, msg: dict):
        request_id = msg.get("request_id")
        if (
            not self.pending_question
            or request_id != self.pending_question_request_id
        ):
            await self._send({
                "type": "error",
                "code": "no_pending_question",
                "message": "no pending question matching request_id",
            })
            return
        if not self.pending_question.done():
            self.pending_question.set_result(msg.get("answer"))

    async def _build_question_callback(self, request_id: str):
        async def ask(spec: dict) -> Any:
            loop = asyncio.get_running_loop()
            self.pending_question = loop.create_future()
            self.pending_question_request_id = request_id
            await self._send({
                "type": "question",
                "request_id": request_id,
                **spec,
            })
            try:
                return await asyncio.wait_for(
                    self.pending_question, timeout=self.question_timeout
                )
            except asyncio.TimeoutError:
                raise QuestionTimeout(
                    f"no answer in {self.question_timeout}s"
                )
            finally:
                self.pending_question = None
                self.pending_question_request_id = None

        return ask

    # ----------------------------------------------------------- disconnect

    async def _on_disconnect(self):
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            try:
                await self.current_task
            except (asyncio.CancelledError, Exception):
                pass
        # Resolve any pending question with a ConnectionError so the awaiting
        # tool can clean up.
        if self.pending_question and not self.pending_question.done():
            self.pending_question.set_exception(
                ConnectionError("client disconnected")
            )

    # --------------------------------------------------------------- helpers

    async def _send(self, event: dict):
        try:
            await self.ws.send_json(event)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning(f"chat-ws: send_json failed: {e}")

    async def _safe_close(self, code: int):
        try:
            await self.ws.close(code=code)
        except Exception:
            pass
