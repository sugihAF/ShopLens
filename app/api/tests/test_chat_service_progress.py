"""Tests for chat_service ↔ progress emitter integration."""
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

    monkeypatch.setattr(service.provider, "generate",
                        lambda *a, **k: _aresult({"_": "r"}))
    monkeypatch.setattr(service.provider, "has_function_call", lambda _r: False)
    monkeypatch.setattr(service.provider, "extract_text", lambda _r: "done")
    monkeypatch.setattr(service.provider, "build_config", lambda **k: None)
    monkeypatch.setattr(service.provider, "build_content",
                        lambda role, msg: {"role": role, "text": msg})

    request = ChatRequest(message="hi", conversation_id=None)
    await service.process_message(request, user_id=None, on_progress=on_progress)

    assert progress_ctx._emitter.get() is None


async def _aresult(v):
    return v


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
