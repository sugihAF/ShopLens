"""WebSocket chat endpoint.

See `docs/superpowers/specs/2026-05-15-chat-websocket-design.md` for the protocol.
"""
from contextlib import asynccontextmanager

from fastapi import APIRouter, WebSocket

from app.db.session import AsyncSessionLocal
from app.services.chat_ws_session import ChatWSSession

router = APIRouter()


@asynccontextmanager
async def _db_session_factory():
    """Default DB session factory; tests override via monkeypatch."""
    async with AsyncSessionLocal() as db:
        yield db


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket):
    """Bidirectional chat over WebSocket."""
    session = ChatWSSession(websocket, db_session_factory=_db_session_factory)
    await session.run()
