# Granular Per-Product Progress Events — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static "Analyzing reviews..." progress row with per-product labels and a live `X/Y` counter that ticks as each parallel URL ingestion completes inside `ingest_reviews_batch`, plus product-name enrichment for search/summary function labels.

**Architecture:** A new `app/api/app/services/progress.py` exposes a request-scoped `contextvars.ContextVar` emitter. `chat_service` sets/resets it around the function-calling loop. Tools in a `SELF_EMITS_PROGRESS` allowlist (just `ingest_reviews_batch` today) own their progress rows by emitting composite `step` ids (`function_name:product_slug`); `chat_service` skips its auto start/done emits for those. Other functions get a richer `label` via a new `label_for(fn_name, args)` helper in `chat_service`. The wire shape gains one additive field — `detail?: str` on the existing `progress` event — rendered as `(3/5)` next to the label.

**Tech Stack:** Python 3.11 / FastAPI / asyncio / `contextvars` / pytest + pytest-asyncio (backend). TypeScript / React / Vite / WebSocket (frontend). Single dev branch: `dev`. Spec: `docs/superpowers/specs/2026-05-18-granular-progress-events-design.md` (commit `26165bf`).

---

## File Structure

**Create:**
- `app/api/app/services/progress.py` — contextvar emitter module + `slug()` helper.
- `app/api/tests/test_progress_emitter.py` — unit tests for the emitter module.
- `app/api/tests/test_chat_service_progress.py` — tests for the chat_service integration (allowlist, label enrichment).
- `app/api/tests/test_ingest_batch_progress.py` — tests for `ingest_reviews_batch` counter cadence and ordering.

**Modify:**
- `app/api/app/services/chat_service.py` — wrap loop body with set/reset, add `SELF_EMITS_PROGRESS`, add `label_for`, replace inline `FUNCTION_LABELS.get(...)` lookups.
- `app/api/app/functions/review_tools.py` — `ingest_reviews_batch` emits its own composite-step events with live counter; preserves input ordering of `results`.
- `app/web/landing-page/src/api/chat.ts` — `ProgressEvent` gains `detail?: string`.
- `app/web/landing-page/src/types/index.ts` — `ProgressStep` gains `detail?: string`.
- `app/web/landing-page/src/hooks/useChat.ts` — propagate `detail` from event into `ProgressStep`.
- `app/web/landing-page/src/pages/ChatPage.tsx` — render `detail` in `ProgressSteps` row.

---

## Task 1: Create the progress emitter module

**Files:**
- Create: `app/api/app/services/progress.py`
- Create: `app/api/tests/test_progress_emitter.py`

- [ ] **Step 1: Write the failing tests**

Create `app/api/tests/test_progress_emitter.py`:

```python
"""Tests for app.services.progress — contextvar-backed emitter."""
import asyncio
import pytest

from app.services import progress


@pytest.mark.asyncio
async def test_emit_is_noop_when_unset():
    """emit() must not raise when no emitter has been set in this context."""
    # Fresh context: nothing should be set.
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
        # Must NOT raise.
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app/api && pytest tests/test_progress_emitter.py -v`
Expected: All FAIL with `ModuleNotFoundError: No module named 'app.services.progress'`

- [ ] **Step 3: Implement the module**

Create `app/api/app/services/progress.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd app/api && pytest tests/test_progress_emitter.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/progress.py app/api/tests/test_progress_emitter.py
git commit -m "feat(progress): contextvar-backed progress emitter module"
```

---

## Task 2: Wire emitter into chat_service.process_message

**Files:**
- Modify: `app/api/app/services/chat_service.py` (add import; wrap loop body in set/reset)
- Create: `app/api/tests/test_chat_service_progress.py` (initial — emitter binding test)

- [ ] **Step 1: Write the failing test**

Create `app/api/tests/test_chat_service_progress.py`:

```python
"""Tests for chat_service ↔ progress emitter integration."""
import asyncio
import pytest

from app.services.chat_service import ChatService
from app.services import progress as progress_ctx
from app.schemas.chat import ChatRequest


@pytest.mark.asyncio
async def test_process_message_binds_emitter_during_loop(db_session, monkeypatch):
    """While process_message is running its function loop, progress.emit() must
    reach the on_progress callback that was passed in."""
    service = ChatService(db_session)
    if service.provider is None:
        pytest.skip("LLM provider not initialized in test environment")

    seen: list[dict] = []

    async def on_progress(ev):
        seen.append(ev)

    # Stub the provider so the loop runs exactly one tool iteration then exits.
    async def fake_generate(contents, config):
        return {"_": "response"}

    call_count = {"n": 0}

    def fake_has_function_call(_resp):
        call_count["n"] += 1
        return call_count["n"] == 1  # True on first iteration, False after

    def fake_extract_function_call(_resp):
        return {"name": "check_product_cache", "args": {"product_name": "Probe"}}

    def fake_extract_function_call_part(_resp):
        return None

    def fake_build_function_response(*_a, **_k):
        return []

    def fake_extract_text(_resp):
        return "ok"

    def fake_build_config(**_k):
        return None

    def fake_build_content(role, msg):
        return {"role": role, "text": msg}

    monkeypatch.setattr(service.provider, "generate", fake_generate)
    monkeypatch.setattr(service.provider, "has_function_call", fake_has_function_call)
    monkeypatch.setattr(service.provider, "extract_function_call", fake_extract_function_call)
    monkeypatch.setattr(service.provider, "extract_function_call_part", fake_extract_function_call_part)
    monkeypatch.setattr(service.provider, "build_function_response", fake_build_function_response)
    monkeypatch.setattr(service.provider, "extract_text", fake_extract_text)
    monkeypatch.setattr(service.provider, "build_config", fake_build_config)
    monkeypatch.setattr(service.provider, "build_content", fake_build_content)

    # Patch the executed tool to emit a custom progress event via the contextvar.
    async def fake_execute_function(_db, _name, _args):
        await progress_ctx.emit({
            "type": "progress",
            "step": "probe_from_tool",
            "status": "running",
            "label": "probe",
        })
        return {"status": "success"}

    monkeypatch.setattr("app.services.chat_service.execute_function", fake_execute_function)

    request = ChatRequest(message="hi", conversation_id=None)
    await service.process_message(request, user_id=None, on_progress=on_progress)

    # The probe event from inside the tool must have reached on_progress.
    assert any(ev.get("step") == "probe_from_tool" for ev in seen), \
        f"emitter was not bound during tool execution; events seen: {seen}"


@pytest.mark.asyncio
async def test_emitter_resets_after_process_message(db_session, monkeypatch):
    """After process_message returns, the contextvar must be back to None."""
    service = ChatService(db_session)
    if service.provider is None:
        pytest.skip("LLM provider not initialized in test environment")

    async def on_progress(_ev):
        pass

    # Minimal stubs — no function calls; just final response.
    monkeypatch.setattr(service.provider, "generate",
                        lambda *a, **k: _aresult({"_": "r"}))
    monkeypatch.setattr(service.provider, "has_function_call", lambda _r: False)
    monkeypatch.setattr(service.provider, "extract_text", lambda _r: "done")
    monkeypatch.setattr(service.provider, "build_config", lambda **k: None)
    monkeypatch.setattr(service.provider, "build_content",
                        lambda role, msg: {"role": role, "text": msg})

    request = ChatRequest(message="hi", conversation_id=None)
    await service.process_message(request, user_id=None, on_progress=on_progress)

    # Outside the call, the contextvar must be unset.
    from app.services import progress as progress_ctx
    assert progress_ctx._emitter.get() is None


async def _aresult(v):
    return v
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app/api && pytest tests/test_chat_service_progress.py::test_process_message_binds_emitter_during_loop -v`
Expected: FAIL — the `probe_from_tool` event is NOT in `seen` because nothing is binding the contextvar.

- [ ] **Step 3: Add the import and wrap the loop body**

In `app/api/app/services/chat_service.py`, add the import near the other `app.services` imports (around line 28):

```python
from app.services import progress as progress_ctx
```

The current structure (verified) is:

```
line 239: try:
line 438:     except ChatCancelled:
line 443:     except Exception as e:
line 447: execution_time = ... (post-try code at same indent as try:)
```

Two edits:

**Edit A** — at line 239 (right before `try:`), insert the set-emitter line:

```python
        progress_token = progress_ctx.set_emitter(on_progress) if on_progress else None
        try:
            # Check circuit breaker before making Gemini calls
            ...
```

**Edit B** — at the end of the `except Exception` block (after line 446, which is `functions_called = []`), and BEFORE the `execution_time = int(...)` line at 447, insert a `finally:` clause at the SAME indent as `try:` (8 spaces):

```python
        except Exception as e:
            logger.error(f"LLM API error: {e}", exc_info=True)
            final_response = "I'm sorry, I encountered an error processing your request. Please try again."
            functions_called = []
        finally:
            if progress_token is not None:
                progress_ctx.reset_emitter(progress_token)

        execution_time = int((time.time() - start_time) * 1000)
```

The `finally:` runs on both success and exception paths (including the re-raised `ChatCancelled`), guaranteeing the contextvar is always restored.

- [ ] **Step 4: Run tests to verify both pass**

Run: `cd app/api && pytest tests/test_chat_service_progress.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_service.py app/api/tests/test_chat_service_progress.py
git commit -m "feat(chat): bind progress emitter contextvar during process_message"
```

---

## Task 3: Add SELF_EMITS_PROGRESS allowlist; skip auto start/done for self-emitters

**Files:**
- Modify: `app/api/app/services/chat_service.py` (add constant; gate the two auto-emit blocks at lines 330 and 365)
- Modify: `app/api/tests/test_chat_service_progress.py` (add test)

- [ ] **Step 1: Append the failing test**

Append to `app/api/tests/test_chat_service_progress.py`:

```python
@pytest.mark.asyncio
async def test_self_emit_allowlist_skips_auto_start_and_done(db_session, monkeypatch):
    """For functions in SELF_EMITS_PROGRESS, chat_service must NOT emit the
    auto start/done events under the bare function-name step."""
    from app.services.chat_service import SELF_EMITS_PROGRESS
    assert "ingest_reviews_batch" in SELF_EMITS_PROGRESS

    service = ChatService(db_session)
    if service.provider is None:
        pytest.skip("LLM provider not initialized in test environment")

    seen: list[dict] = []

    async def on_progress(ev):
        seen.append(ev)

    call_count = {"n": 0}

    async def fake_generate(_c, _cfg):
        return {"_": "r"}

    def fake_has_function_call(_r):
        call_count["n"] += 1
        return call_count["n"] == 1

    def fake_extract_function_call(_r):
        return {"name": "ingest_reviews_batch",
                "args": {"product_name": "Probe", "youtube_urls": ["x"]}}

    monkeypatch.setattr(service.provider, "generate", fake_generate)
    monkeypatch.setattr(service.provider, "has_function_call", fake_has_function_call)
    monkeypatch.setattr(service.provider, "extract_function_call", fake_extract_function_call)
    monkeypatch.setattr(service.provider, "extract_function_call_part", lambda _r: None)
    monkeypatch.setattr(service.provider, "build_function_response", lambda *a, **k: [])
    monkeypatch.setattr(service.provider, "extract_text", lambda _r: "ok")
    monkeypatch.setattr(service.provider, "build_config", lambda **k: None)
    monkeypatch.setattr(service.provider, "build_content",
                        lambda role, msg: {"role": role, "text": msg})

    async def fake_execute_function(_db, _name, _args):
        return {"status": "success"}

    monkeypatch.setattr("app.services.chat_service.execute_function", fake_execute_function)

    request = ChatRequest(message="hi", conversation_id=None)
    await service.process_message(request, user_id=None, on_progress=on_progress)

    # No auto-emit for ingest_reviews_batch under the bare step id.
    bare_steps = [ev for ev in seen if ev.get("step") == "ingest_reviews_batch"]
    assert bare_steps == [], (
        f"chat_service emitted auto start/done for a self-emitting function; "
        f"got: {bare_steps}"
    )


@pytest.mark.asyncio
async def test_non_self_emit_function_still_gets_auto_start_and_done(db_session, monkeypatch):
    """Regression: functions NOT in SELF_EMITS_PROGRESS keep their auto emits."""
    service = ChatService(db_session)
    if service.provider is None:
        pytest.skip("LLM provider not initialized in test environment")

    seen: list[dict] = []

    async def on_progress(ev):
        seen.append(ev)

    call_count = {"n": 0}

    async def fake_generate(_c, _cfg):
        return {"_": "r"}

    def fake_has_function_call(_r):
        call_count["n"] += 1
        return call_count["n"] == 1

    def fake_extract_function_call(_r):
        return {"name": "check_product_cache", "args": {"product_name": "Probe"}}

    monkeypatch.setattr(service.provider, "generate", fake_generate)
    monkeypatch.setattr(service.provider, "has_function_call", fake_has_function_call)
    monkeypatch.setattr(service.provider, "extract_function_call", fake_extract_function_call)
    monkeypatch.setattr(service.provider, "extract_function_call_part", lambda _r: None)
    monkeypatch.setattr(service.provider, "build_function_response", lambda *a, **k: [])
    monkeypatch.setattr(service.provider, "extract_text", lambda _r: "ok")
    monkeypatch.setattr(service.provider, "build_config", lambda **k: None)
    monkeypatch.setattr(service.provider, "build_content",
                        lambda role, msg: {"role": role, "text": msg})
    monkeypatch.setattr(
        "app.services.chat_service.execute_function",
        lambda *a, **k: _aresult({"status": "success"}),
    )

    request = ChatRequest(message="hi", conversation_id=None)
    await service.process_message(request, user_id=None, on_progress=on_progress)

    steps_for_fn = [ev for ev in seen if ev.get("step") == "check_product_cache"]
    statuses = [ev["status"] for ev in steps_for_fn]
    assert "running" in statuses and "done" in statuses, (
        f"expected running+done for check_product_cache; got: {steps_for_fn}"
    )
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd app/api && pytest tests/test_chat_service_progress.py -v`
Expected: `test_self_emit_allowlist_skips_auto_start_and_done` FAILS (constant doesn't exist yet, AND the auto-emits still fire).

- [ ] **Step 3: Add the constant and gate both auto-emit blocks**

In `app/api/app/services/chat_service.py`, immediately after `FUNCTION_LABELS = { ... }` (ends around line 44), add:

```python
# Functions that emit their own progress events under composite step ids
# (e.g. "ingest_reviews_batch:iphone-15-pro"). chat_service skips its auto
# start/done emits for these so they don't produce orphan rows.
# See: docs/superpowers/specs/2026-05-18-granular-progress-events-design.md
SELF_EMITS_PROGRESS = {"ingest_reviews_batch"}
```

Modify the auto-start block (currently lines 330-336). Change:

```python
                # Emit progress: function starting
                if on_progress:
                    await on_progress({
                        "type": "progress",
                        "step": function_name,
                        "status": "running",
                        "label": FUNCTION_LABELS.get(function_name, function_name),
                    })
```

to:

```python
                # Emit progress: function starting (skip for self-emitting tools)
                if on_progress and function_name not in SELF_EMITS_PROGRESS:
                    await on_progress({
                        "type": "progress",
                        "step": function_name,
                        "status": "running",
                        "label": FUNCTION_LABELS.get(function_name, function_name),
                    })
```

Modify the auto-done block (currently lines 365-371) the same way. Change:

```python
                # Emit progress: function done
                if on_progress:
                    await on_progress({
                        "type": "progress",
                        "step": function_name,
                        "status": "done",
                        "label": FUNCTION_LABELS.get(function_name, function_name),
                    })
```

to:

```python
                # Emit progress: function done (skip for self-emitting tools)
                if on_progress and function_name not in SELF_EMITS_PROGRESS:
                    await on_progress({
                        "type": "progress",
                        "step": function_name,
                        "status": "done",
                        "label": FUNCTION_LABELS.get(function_name, function_name),
                    })
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd app/api && pytest tests/test_chat_service_progress.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_service.py app/api/tests/test_chat_service_progress.py
git commit -m "feat(chat): SELF_EMITS_PROGRESS allowlist; skip auto emits for self-emitters"
```

---

## Task 4: Extract `label_for(fn_name, args)` helper with product enrichment

**Files:**
- Modify: `app/api/app/services/chat_service.py` (add helper; replace 3 `FUNCTION_LABELS.get(...)` call sites with `label_for(...)`)
- Modify: `app/api/tests/test_chat_service_progress.py` (add test)

- [ ] **Step 1: Append the failing test**

Append to `app/api/tests/test_chat_service_progress.py`:

```python
def test_label_for_enriches_allowlisted_functions():
    """label_for() must append 'for <product>' for search/summary functions."""
    from app.services.chat_service import label_for

    assert label_for("search_youtube_reviews", {"product_name": "iPhone 15 Pro"}) \
        == "Searching YouTube for iPhone 15 Pro"
    assert label_for("search_blog_reviews", {"product_name": "Galaxy S25"}) \
        == "Searching blog reviews for Galaxy S25"
    assert label_for("get_reviews_summary", {"product_name": "Pixel 8"}) \
        == "Generating summary for Pixel 8"


def test_label_for_falls_back_to_query_arg():
    """label_for() reads `query` if `product_name` is missing."""
    from app.services.chat_service import label_for

    assert label_for("search_youtube_reviews", {"query": "best headphones"}) \
        == "Searching YouTube for best headphones"


def test_label_for_unenriched_function_returns_base_label():
    """Functions not in the enrichment set must return the bare base label."""
    from app.services.chat_service import label_for

    assert label_for("check_product_cache", {"product_name": "X"}) \
        == "Checking product cache"
    assert label_for("find_marketplace_listings", {"product_name": "X"}) \
        == "Finding where to buy"


def test_label_for_unknown_function_returns_function_name():
    """Functions absent from FUNCTION_LABELS fall back to the bare name."""
    from app.services.chat_service import label_for

    assert label_for("brand_new_function", {}) == "brand_new_function"


def test_label_for_missing_args_returns_base_label():
    """No product_name AND no query → return base label, no 'for' suffix."""
    from app.services.chat_service import label_for

    assert label_for("search_youtube_reviews", {}) == "Searching YouTube"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app/api && pytest tests/test_chat_service_progress.py -v -k label_for`
Expected: 5 FAIL with `ImportError: cannot import name 'label_for'`

- [ ] **Step 3: Add the helper and switch the call sites**

In `app/api/app/services/chat_service.py`, immediately after `SELF_EMITS_PROGRESS = {...}` (added in Task 3), add:

```python
# Functions whose progress label should be enriched with the product / query
# argument so users see e.g. "Searching YouTube for iPhone 15 Pro".
LABEL_ENRICHED = {
    "search_youtube_reviews",
    "search_blog_reviews",
    "get_reviews_summary",
}


def label_for(fn_name: str, args: dict) -> str:
    """Build the progress label for a function call.

    - For functions in LABEL_ENRICHED, append "for <product_name or query>".
    - For others, return the bare base label from FUNCTION_LABELS.
    - For unknown functions, return the function name itself.
    """
    base = FUNCTION_LABELS.get(fn_name, fn_name)
    if fn_name in LABEL_ENRICHED:
        target = args.get("product_name") or args.get("query")
        if target:
            return f"{base} for {target}"
    return base
```

Replace the two `FUNCTION_LABELS.get(function_name, function_name)` expressions inside the gated emit blocks (modified in Task 3) with `label_for(function_name, function_args)`. The auto-start block becomes:

```python
                if on_progress and function_name not in SELF_EMITS_PROGRESS:
                    await on_progress({
                        "type": "progress",
                        "step": function_name,
                        "status": "running",
                        "label": label_for(function_name, function_args),
                    })
```

…and the auto-done block analogously. The "Generating response" emit at line ~405 is NOT a function-name event; leave it alone.

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd app/api && pytest tests/test_chat_service_progress.py -v`
Expected: 9 passed (4 from before + 5 new)

- [ ] **Step 5: Commit**

```bash
git add app/api/app/services/chat_service.py app/api/tests/test_chat_service_progress.py
git commit -m "feat(chat): label_for() helper enriches search/summary labels with product"
```

---

## Task 5: `ingest_reviews_batch` emits composite-step events with live counter

**Files:**
- Modify: `app/api/app/functions/review_tools.py` (lines 1036-1120 region — `ingest_reviews_batch`)
- Create: `app/api/tests/test_ingest_batch_progress.py`

- [ ] **Step 1: Write the failing tests**

Create `app/api/tests/test_ingest_batch_progress.py`:

```python
"""Tests for ingest_reviews_batch — emits composite-step progress with counter."""
import asyncio
import pytest

from app.functions import review_tools
from app.services import progress as progress_ctx


@pytest.mark.asyncio
async def test_emits_start_with_zero_counter(monkeypatch):
    """ingest_reviews_batch must emit a 'running' event with detail '0/N' at start."""
    seen: list[dict] = []

    async def emitter(ev):
        seen.append(ev)

    async def fake_yt(_session, _args):
        return {"status": "success"}

    async def fake_blog(_session, _args):
        return {"status": "success"}

    monkeypatch.setattr(review_tools, "ingest_youtube_review", fake_yt)
    monkeypatch.setattr(review_tools, "ingest_blog_review", fake_blog)

    token = progress_ctx.set_emitter(emitter)
    try:
        await review_tools.ingest_reviews_batch(
            None,
            {"product_name": "iPhone 15 Pro",
             "youtube_urls": ["a", "b"],
             "blog_urls": ["c"]},
        )
    finally:
        progress_ctx.reset_emitter(token)

    # First event: 0/3 running.
    assert seen[0]["status"] == "running"
    assert seen[0]["detail"] == "0/3"
    assert seen[0]["step"] == "ingest_reviews_batch:iphone-15-pro"
    assert seen[0]["label"] == "Analyzing reviews for iPhone 15 Pro"


@pytest.mark.asyncio
async def test_emits_n_plus_one_events_for_n_urls(monkeypatch):
    """For N=4 URLs: 1 start (0/4) + 3 progress ticks (1/4..3/4) + 1 done = 5 events."""
    seen: list[dict] = []

    async def emitter(ev):
        seen.append(ev)

    async def fake_ingest(_session, _args):
        return {"status": "success"}

    monkeypatch.setattr(review_tools, "ingest_youtube_review", fake_ingest)
    monkeypatch.setattr(review_tools, "ingest_blog_review", fake_ingest)

    token = progress_ctx.set_emitter(emitter)
    try:
        await review_tools.ingest_reviews_batch(
            None,
            {"product_name": "Probe",
             "youtube_urls": ["y1", "y2"],
             "blog_urls": ["b1", "b2"]},
        )
    finally:
        progress_ctx.reset_emitter(token)

    assert len(seen) == 5, f"expected 5 events for N=4; got {len(seen)}: {seen}"

    # All under the same composite step id.
    assert all(ev["step"] == "ingest_reviews_batch:probe" for ev in seen)

    # Cadence: 0/4 (running), 1/4 (running), 2/4 (running), 3/4 (running), done (no detail)
    details = [ev.get("detail") for ev in seen[:-1]]
    assert details == ["0/4", "1/4", "2/4", "3/4"], f"counter cadence wrong: {details}"

    assert seen[-1]["status"] == "done"
    assert seen[-1].get("detail") in (None, ""), \
        f"done event must not carry detail; got: {seen[-1]}"


@pytest.mark.asyncio
async def test_preserves_input_order_in_results(monkeypatch):
    """Replacing gather with as_completed must not reorder the `results` list.

    Force completion order INVERSE to input order by sleeping based on URL:
    u1 sleeps longest, u3 shortest. The aggregated `results` list must still
    be in input order [u1, u2, u3].
    """
    sleep_by_url = {"u1": 0.03, "u2": 0.02, "u3": 0.01}

    async def fake_yt(_session, args):
        url = args["video_url"]
        await asyncio.sleep(sleep_by_url.get(url, 0))
        return {"status": "success", "url": url}

    monkeypatch.setattr(review_tools, "ingest_youtube_review", fake_yt)

    result = await review_tools.ingest_reviews_batch(
        None,
        {"product_name": "Probe",
         "youtube_urls": ["u1", "u2", "u3"]},
    )

    urls_in_result = [r.get("url") for r in result["results"]]
    assert urls_in_result == ["u1", "u2", "u3"], \
        f"results out of input order; got: {urls_in_result}"


@pytest.mark.asyncio
async def test_counter_advances_on_failures_too(monkeypatch):
    """A raising ingest still counts toward the counter — user cares about slot completion."""
    seen: list[dict] = []

    async def emitter(ev):
        seen.append(ev)

    async def fake_yt(_session, _args):
        raise RuntimeError("boom")

    monkeypatch.setattr(review_tools, "ingest_youtube_review", fake_yt)

    token = progress_ctx.set_emitter(emitter)
    try:
        result = await review_tools.ingest_reviews_batch(
            None,
            {"product_name": "Probe", "youtube_urls": ["u1", "u2"]},
        )
    finally:
        progress_ctx.reset_emitter(token)

    # Cadence still 0/2, 1/2, done (3 events for N=2).
    assert len(seen) == 3
    assert [ev.get("detail") for ev in seen[:-1]] == ["0/2", "1/2"]
    assert result["failed"] == 2


@pytest.mark.asyncio
async def test_no_emitter_is_a_noop(monkeypatch):
    """When no emitter is bound, ingest_reviews_batch must still work normally."""
    async def fake_yt(_s, _a):
        return {"status": "success"}

    monkeypatch.setattr(review_tools, "ingest_youtube_review", fake_yt)

    # NO set_emitter call.
    result = await review_tools.ingest_reviews_batch(
        None,
        {"product_name": "Probe", "youtube_urls": ["u1", "u2"]},
    )
    assert result["succeeded"] == 2
    assert result["failed"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app/api && pytest tests/test_ingest_batch_progress.py -v`
Expected: First four tests FAIL (no progress events emitted); the last (`test_no_emitter_is_a_noop`) may already pass if the existing implementation handles the args correctly.

- [ ] **Step 3: Rewrite ingest_reviews_batch with counter + ordering preservation**

In `app/api/app/functions/review_tools.py`, add the import at the top (alongside the existing `from app.services...` imports):

```python
from app.services import progress as progress_ctx
```

Replace the body of `ingest_reviews_batch` (currently `app/api/app/functions/review_tools.py:1036-1120`) with this. The signature and docstring stay; only the body changes:

```python
@register_function("ingest_reviews_batch")
async def ingest_reviews_batch(db: AsyncSession, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ingest multiple YouTube and blog reviews in parallel.

    Emits per-batch progress under step "ingest_reviews_batch:<product-slug>"
    with a live "k/N" counter as each parallel task completes. See:
    docs/superpowers/specs/2026-05-18-granular-progress-events-design.md
    """
    product_name = args.get("product_name", "").strip()
    youtube_urls = args.get("youtube_urls") or []
    blog_urls = args.get("blog_urls") or []

    if not product_name:
        return {"error": "product_name is required"}

    if not youtube_urls and not blog_urls:
        return {"error": "At least one of youtube_urls or blog_urls is required"}

    semaphore = asyncio.Semaphore(5)

    async def _ingest_one(idx: int, ingest_fn, fn_args: Dict[str, Any]):
        """Run a single ingestion with its own DB session; tag with input index."""
        async with semaphore:
            async with AsyncSessionLocal() as session:
                try:
                    result = await ingest_fn(session, fn_args)
                    await session.commit()
                    return idx, result
                except Exception as e:
                    await session.rollback()
                    return idx, {"status": "error", "error": str(e)}

    # Build indexed task list so we can restore input order after as_completed.
    coros = []
    next_idx = 0
    for url in youtube_urls:
        coros.append(_ingest_one(next_idx, ingest_youtube_review,
                                 {"video_url": url, "product_name": product_name}))
        next_idx += 1
    for url in blog_urls:
        coros.append(_ingest_one(next_idx, ingest_blog_review,
                                 {"url": url, "product_name": product_name}))
        next_idx += 1

    total = len(coros)
    step_id = f"ingest_reviews_batch:{progress_ctx.slug(product_name)}"
    label = f"Analyzing reviews for {product_name}"

    logger.info(
        f"Batch ingestion: {len(youtube_urls)} YouTube + {len(blog_urls)} blog URLs in parallel"
    )

    # Emit start event with 0/N.
    await progress_ctx.emit({
        "type": "progress",
        "step": step_id,
        "status": "running",
        "label": label,
        "detail": f"0/{total}",
    })

    # Run all in parallel; tick the counter as each finishes.
    results_by_idx: Dict[int, Any] = {}
    futures = [asyncio.ensure_future(c) for c in coros]
    done_count = 0
    for finished in asyncio.as_completed(futures):
        try:
            idx, result = await finished
        except Exception as e:
            # _ingest_one already catches internally; this branch shouldn't fire,
            # but if it does we don't know which idx — slot it under -done_count
            # to keep the counter accurate without colliding with real indices.
            idx = -1 - done_count
            result = e
        results_by_idx[idx] = result
        done_count += 1
        # Tick AFTER each non-final completion (the final one is folded into `done`).
        if done_count < total:
            await progress_ctx.emit({
                "type": "progress",
                "step": step_id,
                "status": "running",
                "label": label,
                "detail": f"{done_count}/{total}",
            })

    # Reassemble in input order (negative idx = synthetic failures, appended).
    ordered = [results_by_idx[i] for i in range(total) if i in results_by_idx]
    for i in sorted(k for k in results_by_idx if k < 0):
        ordered.append(results_by_idx[i])

    # Aggregate.
    succeeded = 0
    failed = 0
    details = []
    for result in ordered:
        if isinstance(result, Exception):
            failed += 1
            details.append({"status": "error", "error": str(result)})
        elif isinstance(result, dict):
            if result.get("status") in ("success", "already_exists"):
                succeeded += 1
            else:
                failed += 1
            details.append(result)
        else:
            failed += 1
            details.append({"status": "error", "error": "Unknown result type"})

    logger.info(f"Batch ingestion complete: {succeeded} succeeded, {failed} failed")

    # Emit final `done` event (no detail).
    await progress_ctx.emit({
        "type": "progress",
        "step": step_id,
        "status": "done",
        "label": label,
    })

    return {
        "status": "success" if succeeded > 0 else "error",
        "succeeded": succeeded,
        "failed": failed,
        "total": total,
        "results": details,
    }
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd app/api && pytest tests/test_ingest_batch_progress.py -v`
Expected: 5 passed

Also re-run the affected adjacent test files to catch regressions:

Run: `cd app/api && pytest tests/test_review_pipeline.py tests/test_functions.py -v`
Expected: same number of passes as before this task (verify by running on the previous commit if uncertain).

- [ ] **Step 5: Commit**

```bash
git add app/api/app/functions/review_tools.py app/api/tests/test_ingest_batch_progress.py
git commit -m "feat(ingest): emit composite-step progress with live counter in batch ingestion"
```

---

## Task 6: Add `detail?: string` to frontend `ProgressEvent` and `ProgressStep` types

**Files:**
- Modify: `app/web/landing-page/src/api/chat.ts` (line 45-50 — `ProgressEvent` interface)
- Modify: `app/web/landing-page/src/types/index.ts` (line 102-106 — `ProgressStep` interface)

(No tests — the frontend has no unit-test infra today; types are checked by `tsc`.)

- [ ] **Step 1: Add `detail` to `ProgressEvent`**

In `app/web/landing-page/src/api/chat.ts`, replace the `ProgressEvent` interface (lines 45-50):

```typescript
export interface ProgressEvent {
  request_id: string
  step: string
  label?: string
  status: 'running' | 'done'
  detail?: string
}
```

- [ ] **Step 2: Add `detail` to `ProgressStep`**

In `app/web/landing-page/src/types/index.ts`, replace the `ProgressStep` interface (lines 102-106):

```typescript
export interface ProgressStep {
  step: string
  label: string
  status: 'running' | 'done'
  detail?: string
}
```

- [ ] **Step 3: Type-check**

Run: `cd app/web/landing-page && npm run build` (or whatever the project's `tsc`-running script is — fall back to `npx tsc --noEmit` if no script).
Expected: no type errors introduced by these changes. Existing callers don't pass `detail`, so optional-ness keeps them valid.

- [ ] **Step 4: Commit**

```bash
git add app/web/landing-page/src/api/chat.ts app/web/landing-page/src/types/index.ts
git commit -m "feat(web): add optional detail field to ProgressEvent and ProgressStep"
```

---

## Task 7: Propagate `detail` from event → ProgressStep in `useChat`

**Files:**
- Modify: `app/web/landing-page/src/hooks/useChat.ts` (lines 19-34 — `onProgress` handler)

- [ ] **Step 1: Update the `onProgress` handler**

In `app/web/landing-page/src/hooks/useChat.ts`, locate the block (lines 19-34):

```typescript
      onProgress: (event) => {
        if (event.request_id !== currentRequestIdRef.current) return
        setProgressSteps((prev) => {
          const idx = prev.findIndex((s) => s.step === event.step)
          const step: ProgressStep = {
            step: event.step,
            label: event.label ?? event.step,
            status: event.status,
          }
          if (idx >= 0) {
            const updated = [...prev]
            updated[idx] = step
            return updated
          }
          return [...prev, step]
        })
      },
```

Add `detail` to the `ProgressStep` construction:

```typescript
      onProgress: (event) => {
        if (event.request_id !== currentRequestIdRef.current) return
        setProgressSteps((prev) => {
          const idx = prev.findIndex((s) => s.step === event.step)
          const step: ProgressStep = {
            step: event.step,
            label: event.label ?? event.step,
            status: event.status,
            detail: event.detail,
          }
          if (idx >= 0) {
            const updated = [...prev]
            updated[idx] = step
            return updated
          }
          return [...prev, step]
        })
      },
```

- [ ] **Step 2: Type-check**

Run: `cd app/web/landing-page && npm run build`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add app/web/landing-page/src/hooks/useChat.ts
git commit -m "feat(web): propagate progress detail field into ProgressStep state"
```

---

## Task 8: Render `detail` in `ProgressSteps` component

**Files:**
- Modify: `app/web/landing-page/src/pages/ChatPage.tsx` (line 112 — the rendered span)

- [ ] **Step 1: Add detail to the rendered text**

In `app/web/landing-page/src/pages/ChatPage.tsx`, locate the line (currently line 112):

```tsx
            {step.label}{step.status === 'running' ? '...' : ''}
```

Replace with:

```tsx
            {step.label}{step.detail ? ` (${step.detail})` : ''}{step.status === 'running' ? '...' : ''}
```

- [ ] **Step 2: Type-check**

Run: `cd app/web/landing-page && npm run build`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add app/web/landing-page/src/pages/ChatPage.tsx
git commit -m "feat(web): render progress detail (counter) next to label in ProgressSteps"
```

---

## Task 9: Manual smoke test

No code changes. Verifies end-to-end behavior on the dev stack.

- [ ] **Step 1: Start the dev stack**

Run: `docker-compose -f docker-compose.dev.yml up --build`
Wait for the API to log "Application startup complete" and the web to log Vite's "ready in".

- [ ] **Step 2: Run a multi-product query**

Open the app at `http://localhost:5173`, navigate to `/chat`, send:

> best noise-canceling headphones under $400

- [ ] **Step 3: Verify the progress rows**

While the pipeline runs (expect ~5 minutes), confirm the progress panel shows rows like:

```
Checking product cache... done
Searching YouTube for Sony WH-1000XM5... done
Searching blog reviews for Sony WH-1000XM5... done
Analyzing reviews for Sony WH-1000XM5 (3/5)...
Searching YouTube for Bose QC Ultra...
...
```

Confirm:
- Each product gets its own "Analyzing reviews for <name>" row.
- The counter ticks upward visibly during the batch (e.g. `0/5` → `1/5` → ... → `5/5`).
- The row transitions to a checkmark (`done`) without the counter when the batch completes.
- Search/summary rows include the product name.
- Single-product fast paths (e.g. `check_product_cache`) keep their unchanged labels.

- [ ] **Step 4: Verify nothing regresses on the REST endpoint**

Run: `cd app/api && pytest tests/test_chat.py tests/test_chat_service_integration.py -v`
Expected: same number of passes as before this work.

- [ ] **Step 5: (Optional) Verify the run_pipeline.py script still works**

Run: `docker exec -it shoplens-api-dev python run_pipeline.py "Probe Product"` (any tracked product is fine).
Expected: completes without raising; no `progress` errors in logs (the script doesn't bind an emitter, so all `progress.emit(...)` calls are no-ops).

- [ ] **Step 6: No commit needed**

This task is verification only.

---

## Done criteria

- All five new pytest files pass on a clean run of the api test suite.
- The dev-stack smoke test shows per-product rows with a live ticking counter for a 4+ product query.
- `git log --oneline dev` shows eight feature commits stacked on `26165bf` (the spec commit) — one per Task 1–8.
- `docs/superpowers/plans/2026-05-18-granular-progress-events.md` (this file) and `docs/superpowers/specs/2026-05-18-granular-progress-events-design.md` are both committed on `dev`.
