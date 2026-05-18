# Granular Per-Product Progress Events — Design Spec

**Date:** 2026-05-18
**Status:** Draft (pending user review)
**Owner:** sugihAF
**Tracking:** `next_implementation.md` item #21

## Goal

Replace the single static "Analyzing reviews..." progress row that hangs for 5+ minutes during multi-product queries with a per-product label and a live `X/Y` counter that ticks as each parallel URL ingestion completes.

Today, a query like *"best noise-canceling headphones under $400"* triggers `ingest_reviews_batch` once per product (4+ products, ~80s each, sequential). The user sees one frozen "Analyzing reviews..." entry for the entire window and abandons the UI long before the 10-minute client timeout — even though work is happening.

## Non-Goals

- **No token-level streaming from Gemini.** Already deferred in `2026-05-15-chat-websocket-design.md`. Reserved `token` event type remains unused.
- **No per-URL cancellation inside a batch.** A `cancel` message stops the function-loop at the next iteration boundary; in-flight parallel URL tasks finish on their own. Matches today's behavior.
- **No new WebSocket event types.** Reuse the existing `progress` type with one additive field (`detail`).
- **No progress events from inside `ingest_youtube_review` / `ingest_blog_review` internals** (Firecrawl fetch vs Gemini analyse sub-steps). Out of scope.
- **No protocol-table update to `2026-05-15-chat-websocket-design.md`** in this PR. Noted as a follow-up.

## Approach (chosen)

Two complementary pieces:

1. **Label enrichment** for fast functions (`search_youtube_reviews`, `search_blog_reviews`, `get_reviews_summary`) — done entirely in `chat_service`, no tool-side changes. The existing function-level start/done emits get a richer label like *"Searching YouTube for iPhone 15 Pro"*.

2. **Sub-progress ticks** for the slow function (`ingest_reviews_batch`) — the tool itself emits `running` events with a `detail: "k/N"` counter via a request-scoped `contextvars.ContextVar`. To avoid a duplicate row, `chat_service` skips its auto-emit for tools in a `SELF_EMITS_PROGRESS` allowlist.

### Rejected alternatives

- **Pass `on_progress` as an explicit kwarg through `execute_function`** — signature churn for ~7 functions that mostly don't care about progress. Loses the request-scoped property; would also need to be passed through every helper inside `review_tools`.
- **`asyncio.Queue` with a consumer task** — adds a moving part (the consumer's lifecycle, draining on cancel) and buys nothing over a direct async callback.
- **Per-URL individual progress events** (one row per URL) — UI list balloons to 20+ rows for a 4-product query, harder to scan than a per-product counter.
- **Per-product label only, no counter** — addresses the "which product" question but not the "is anything still happening?" question. The counter is the cheapest liveness signal.

## Protocol

### Wire shape — `progress` event (extended)

```json
{
  "type": "progress",
  "request_id": "<uuid>",
  "step": "<function_name>[:<product_slug>]",
  "status": "running" | "done",
  "label": "<human-readable>",
  "detail": "<optional, e.g. \"3/5\">"
}
```

- `step` — for tools in `SELF_EMITS_PROGRESS`, the tool emits a composite id `f"{function_name}:{slug(product_name)}"`. For other tools, `step` remains the function name as today. The frontend dedupes by `step`, so composite ids produce one row per product that updates in place.
- `label` — for label-enriched functions, includes the product/query (e.g. *"Searching YouTube for iPhone 15 Pro"*). For self-emitting tools, the tool sets it (e.g. *"Analyzing reviews for iPhone 15 Pro"*).
- `detail` — additive, optional string. Rendered to the right of `label` in parentheses. Omitted for non-counting events and for `done` events.
- `status` — unchanged.

### Wire compatibility

- `detail` is additive — old clients ignore unknown fields.
- The nginx WS proxy passes frames untouched.
- The `2026-05-15-chat-websocket-design.md` `progress` row already uses an open payload shape; documenting `detail` there is a follow-up edit, not a blocker.

### Counter cadence (per `ingest_reviews_batch` call)

For a batch of N URLs:

1. One `running` event at start with `detail: "0/N"`.
2. One `running` event per parallel task completion: `detail: "1/N"`, `"2/N"`, ..., `"N-1/N"`. (The final completion is folded into the `done` event below.)
3. One `done` event with no `detail`.

Total: `N + 1` events. For N=5, six events. Negligible bandwidth.

## Server Architecture

### New module — `app/api/app/services/progress.py`

A thin contextvar-backed emitter. Tools call `progress.emit(...)`; `chat_service` sets/resets the emitter around the function-calling loop. Default state (no emitter set) is a no-op — required for the REST `POST /chat` endpoint, `run_pipeline.py`, and tests, none of which provide a WebSocket-relay callback.

Public API:

```python
ProgressEmitter = Callable[[Dict[str, str]], Awaitable[None]]

def set_emitter(emit: Optional[ProgressEmitter]) -> contextvars.Token: ...
def reset_emitter(token: contextvars.Token) -> None: ...
async def emit(event: Dict[str, str]) -> None: ...  # no-op if unset
```

`emit()` swallows any exception from the underlying callback (logged at WARNING) so a closed WebSocket never breaks the function loop.

### `chat_service.py` changes

1. **Wrap the function-loop** in `try/finally` that calls `progress.set_emitter(on_progress)` on entry and `reset_emitter(token)` on exit. Only when `on_progress` is not None.
2. **Define `SELF_EMITS_PROGRESS = {"ingest_reviews_batch"}`**. Skip both the auto-start AND auto-done emits at the existing call sites for functions in this set. The tool owns the entire row lifecycle for its composite `step` id. (Leaving the auto-done in place would create an orphan `"Analyzing reviews... done"` row under the bare `ingest_reviews_batch` step id, separate from the composite product rows — visually noisy.)

3. **Introduce `label_for(fn_name: str, args: dict) -> str`** — replaces the inline `FUNCTION_LABELS.get(...)` lookup. Adds product context to a small allowlist:

   ```python
   LABEL_ENRICHED = {"search_youtube_reviews", "search_blog_reviews", "get_reviews_summary"}
   def label_for(fn_name, args):
       base = FUNCTION_LABELS.get(fn_name, fn_name)
       if fn_name in LABEL_ENRICHED:
           target = args.get("product_name") or args.get("query")
           if target:
               return f"{base} for {target}"
       return base
   ```

### `review_tools.ingest_reviews_batch` changes

1. **Import `progress` module** at top.
2. **Compute `step_id = f"ingest_reviews_batch:{_slug(product_name)}"`** and `label = f"Analyzing reviews for {product_name}"`.
3. **Replace `asyncio.gather(*tasks)`** with an `as_completed`-style loop that ticks `done_count` after each completion. Because `as_completed` doesn't preserve task→input ordering, wrap each `_ingest_one` so it returns `(idx, result)`; reassemble into the original `results` list after the loop.
4. **Emit** at start (`detail: "0/N"`), after each non-final completion (`detail: "k/N"`), and `done` at the end.

The existing aggregation block (lines 1095–1110) is unchanged — it operates on the reassembled-by-idx `results` list.

### Slug helper

A small `_slug(name)` in `progress.py` (or co-located in `review_tools.py` — implementation choice during plan). Lowercase, non-alphanumerics → `-`, strip leading/trailing `-`. Used only to make the step id stable and URL-safe; never user-visible.

## Frontend Architecture

### Type changes — `app/web/landing-page/src/types/index.ts`

```ts
export interface ProgressStep {
  step: string
  label: string
  status: 'running' | 'done'
  detail?: string  // NEW
}
```

### API changes — `app/web/landing-page/src/api/chat.ts`

```ts
export interface ProgressEvent {
  request_id: string
  step: string
  label?: string
  status: 'running' | 'done'
  detail?: string  // NEW
}
```

### Hook changes — `app/web/landing-page/src/hooks/useChat.ts`

In the `onProgress` handler (lines 21-34), include `detail` when constructing the `ProgressStep`:

```ts
const step: ProgressStep = {
  step: event.step,
  label: event.label ?? event.step,
  status: event.status,
  detail: event.detail,
}
```

No new state shape — the existing dedupe-by-`step` logic handles per-product rows for free.

### Component changes — `app/web/landing-page/src/pages/ChatPage.tsx`

In `ProgressSteps`, line 112, render the detail:

```tsx
{step.label}{step.detail ? ` (${step.detail})` : ''}{step.status === 'running' ? '...' : ''}
```

No structural changes to the component.

## Error handling

- **WebSocket already closed when emit fires** → `progress.emit()` catches, logs WARNING, returns. Function loop continues.
- **Tool raises before its first emit** → no rows appear for that product. Matches today's behavior for any function that errors before completion.
- **One parallel URL ingestion raises inside the batch** → it's still counted toward `done_count` (the user cares about slot completion, not success). The existing aggregation classifies it as `failed`. No special-case event.
- **Cancel mid-batch** — `cancel_event.is_set()` is checked at the function-loop iteration boundary in `chat_service`. The in-flight `ingest_reviews_batch` finishes naturally; its sub-progress events keep firing harmlessly until completion. `cancelled` event is emitted by the WS session after the loop unwinds.

## Testing

New test files under `app/api/tests/`:

- **`test_progress_emitter.py`** — emitter is a no-op when unset; payload passes through when set; raising callback doesn't propagate.
- **`test_chat_service_progress.py`** — spy on `on_progress`; assert `SELF_EMITS_PROGRESS` skips the auto-start for `ingest_reviews_batch`; assert `label_for` enriches `search_youtube_reviews` / `search_blog_reviews` / `get_reviews_summary` and leaves others alone.
- **`test_ingest_batch_progress.py`** — monkeypatch `ingest_youtube_review` and `ingest_blog_review` to return immediately with known payloads; assert N+1 events fire in correct order; assert the final aggregated `results` order matches the input URL order (regression on the `as_completed` reorder).

No frontend unit tests. Manual smoke test: dev stack up, run the canonical multi-product query, confirm the chat shows one row per product with a counter that ticks.

## Rollout

- **Single PR.** No feature flag — the wire shape is additive and backend changes are pure no-ops when `on_progress` is None.
- **Branch:** `dev` (current working branch).
- **Backend changes are safe for** `POST /api/v1/chat` and `run_pipeline.py` — neither sets an emitter, so all new code paths are no-ops there.
- **Manual smoke after merge:** dev stack up, run *"best noise-canceling headphones under $400"*. Expect rows like `Analyzing reviews for Sony WH-1000XM5 (3/5)...` updating live, one per product.

## Follow-ups (not in this PR)

- Update `docs/superpowers/specs/2026-05-15-chat-websocket-design.md` Protocol table to document the optional `detail` field on `progress`.
- Consider extending sub-progress to `ingest_blog_review` (Firecrawl fetch + Gemini analyse are each ~30s, currently a single black box).
- If users still find batch waits opaque, add per-URL events behind a "verbose" toggle.
