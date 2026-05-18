"""
Request-scoped progress emitter for the chat function-calling loop.

`chat_service.process_message` calls `set_emitter(on_progress)` on entry and
`reset_emitter(token)` on exit. Tools deep in the call stack call `emit(...)`
without needing to thread a callback through their signatures. When no emitter
is set (REST endpoint, run_pipeline.py, tests), `emit()` is a no-op.

See: docs/superpowers/specs/2026-05-18-granular-progress-events-design.md
"""
from __future__ import annotations

import contextvars
import logging
import re
from typing import Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

ProgressEmitter = Callable[[Dict[str, str]], Awaitable[None]]

_emitter: contextvars.ContextVar[Optional[ProgressEmitter]] = contextvars.ContextVar(
    "shoplens_progress_emitter", default=None
)


def set_emitter(emit_fn: Optional[ProgressEmitter]) -> contextvars.Token:
    """Bind an emitter to the current async context. Returns a reset token."""
    return _emitter.set(emit_fn)


def reset_emitter(token: contextvars.Token) -> None:
    """Restore the previous emitter binding."""
    _emitter.reset(token)


async def emit(event: Dict[str, str]) -> None:
    """Fire-and-forget progress event. No-op when no emitter is set.

    Any exception raised by the emitter is logged at WARNING and swallowed —
    a closed WebSocket must not break the function-calling loop.
    """
    fn = _emitter.get()
    if fn is None:
        return
    try:
        await fn(event)
    except Exception:
        logger.warning("progress emit failed", exc_info=True)


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    """Make a stable step-id suffix from a free-text name."""
    return _SLUG_RE.sub("-", name.lower()).strip("-")
