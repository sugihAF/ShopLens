"""Tests for app.services.progress — contextvar-backed emitter."""
import asyncio
import pytest

from app.services import progress


@pytest.mark.asyncio
async def test_emit_is_noop_when_unset():
    """emit() must not raise when no emitter has been set in this context."""
    await progress.emit({"type": "progress", "step": "x", "status": "running"})


@pytest.mark.asyncio
async def test_emit_passes_payload_to_set_emitter():
    """When an emitter is set, emit() forwards the exact payload to it."""
    seen: list[dict] = []

    async def capture(ev):
        seen.append(ev)

    token = progress.set_emitter(capture)
    try:
        await progress.emit({"type": "progress", "step": "a", "status": "running"})
        await progress.emit({"type": "progress", "step": "a", "status": "done"})
    finally:
        progress.reset_emitter(token)

    assert seen == [
        {"type": "progress", "step": "a", "status": "running"},
        {"type": "progress", "step": "a", "status": "done"},
    ]


@pytest.mark.asyncio
async def test_emit_swallows_emitter_exceptions():
    """A raising emitter must not propagate — progress is best-effort."""
    async def explode(_ev):
        raise RuntimeError("ws closed")

    token = progress.set_emitter(explode)
    try:
        await progress.emit({"type": "progress", "step": "x", "status": "running"})
    finally:
        progress.reset_emitter(token)


@pytest.mark.asyncio
async def test_reset_clears_emitter():
    """After reset_emitter, emit() must be a no-op again."""
    seen: list[dict] = []

    async def capture(ev):
        seen.append(ev)

    token = progress.set_emitter(capture)
    progress.reset_emitter(token)

    await progress.emit({"type": "progress", "step": "x", "status": "running"})
    assert seen == []


def test_slug_basic():
    """slug() lowercases and replaces non-alphanumerics with hyphens."""
    assert progress.slug("iPhone 15 Pro") == "iphone-15-pro"
    assert progress.slug("Sony WH-1000XM5") == "sony-wh-1000xm5"
    assert progress.slug("  Galaxy   S25  ") == "galaxy-s25"
    assert progress.slug("Pixel 8a (Obsidian)") == "pixel-8a-obsidian"
    assert progress.slug("") == ""
