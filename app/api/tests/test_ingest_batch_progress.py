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
    assert all(ev["step"] == "ingest_reviews_batch:probe" for ev in seen)

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

    assert len(seen) == 3
    assert [ev.get("detail") for ev in seen[:-1]] == ["0/2", "1/2"]
    assert result["failed"] == 2


@pytest.mark.asyncio
async def test_no_emitter_is_a_noop(monkeypatch):
    """When no emitter is bound, ingest_reviews_batch must still work normally."""
    async def fake_yt(_s, _a):
        return {"status": "success"}

    monkeypatch.setattr(review_tools, "ingest_youtube_review", fake_yt)

    result = await review_tools.ingest_reviews_batch(
        None,
        {"product_name": "Probe", "youtube_urls": ["u1", "u2"]},
    )
    assert result["succeeded"] == 2
    assert result["failed"] == 0
