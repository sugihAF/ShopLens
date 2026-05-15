# Chat WebSocket — Design Spec

**Date:** 2026-05-15
**Status:** Draft (pending user review)
**Owner:** sugihAF

## Goal

Replace the existing Server-Sent Events chat stream (`POST /api/v1/chat/stream`) with a bidirectional WebSocket endpoint (`WS /api/v1/chat/ws`). The new endpoint enables three product behaviors that SSE cannot support cleanly:

1. **Cancel** the in-flight chat turn while the function-calling pipeline is still running.
2. **Follow-up messages** sent over the same connection; a new message implicitly cancels the prior in-flight turn ("supersede").
3. **Interactive tool confirmation** (plumbed but not wired to any tool on day one) — the pipeline can ask the user a question mid-flight and resume on their answer.

The non-streaming `POST /api/v1/chat` REST endpoint is left untouched for non-realtime callers (tests, scripts, external integrations).

## Non-Goals

- **No stream resume** after disconnect/reconnect. If the client drops mid-pipeline, the in-flight task is cancelled; the client fetches whatever was persisted via the existing conversation REST endpoints. Designed-in YAGNI.
- **No per-tool wiring of `on_question`** on day one — the plumbing exists, but no review-pipeline tool calls it yet. That wiring is a separate, smaller change.
- **No `python-socketio`, no Redis pub/sub.** Native FastAPI WebSocket; single API replica today, refactor to Redis pub/sub later if/when we scale horizontally.
- **No new notifications channel** (watchlist alerts, price drops). Out of scope; would be a separate WS endpoint and is the natural next step after this lands.

## Approach (chosen)

Native FastAPI WebSocket with a per-connection session supervisor object.

**Rejected alternatives:**

- **`python-socketio`** — adds a non-standard protocol on top of WebSocket; rooms/acks/auto-reconnect aren't load-bearing for replacing the chat stream. Auto-reconnect is a client concern (a small JS helper).
- **Redis pub/sub from day one** — solves a problem we don't have (horizontal scaling) and doubles the design surface. The current chat flow is already in-process; adding a broker requires no infrastructure win in return.
- **Keep SSE in parallel** — the user explicitly chose "replace"; running both surfaces would double the test matrix without buying anything.

## Protocol

**Endpoint:** `WS /api/v1/chat/ws`

### Auth — first-message protocol

1. Client connects; server `accept()`s without checking auth.
2. Server waits up to 5s for `{type: "auth", token: "<bearer>" | null}`.
3. Server resolves user via `decode_token` → `Optional[int]`. `token: null` and `token: "<invalid>"` both resolve to `user_id: None` (anonymous), matching the existing `get_current_user_id` behavior on the REST endpoint.
4. Server replies `{type: "ready", user_id: int | null}`.
5. If no `auth` message within 5s, or the frame is malformed JSON / missing the `type` field, close with code `4401`.

Rationale for first-message instead of query-string token: query strings appear in nginx access logs and browser history; placing the JWT in a WebSocket frame body keeps it out of those logs.

### Client → Server messages

| `type` | Payload | Behavior |
|---|---|---|
| `auth` | `{ token: str \| null }` | One-shot; only valid as the first message |
| `message` | `{ request_id: str, text: str, conversation_id?: UUID }` | Start a new turn; auto-cancels any in-flight request on this connection |
| `cancel` | `{ request_id: str }` | Abort the named in-flight request |
| `confirm` | `{ request_id: str, answer: any }` | Response to a server `question` event |
| `ping` | `{}` | Heartbeat |

### Server → Client events

| `type` | Payload | When |
|---|---|---|
| `ready` | `{ user_id: int \| null }` | After successful auth |
| `progress` | `{ request_id, step, status: "start" \| "done", message? }` | Function-loop step boundaries |
| `token` | `{ request_id, text }` | (Reserved for future token-level streaming from Gemini — not emitted in v1) |
| `question` | `{ request_id, prompt, choices?: list, schema?: jsonschema }` | Mid-pipeline ask (no tool emits this in v1) |
| `complete` | `{ request_id, data: ChatResponse }` | Final response; same shape as REST `POST /chat` |
| `cancelled` | `{ request_id, reason: "user" \| "superseded" }` | Cancel acknowledged |
| `error` | `{ request_id?, code, message }` | Recoverable error; connection stays open |
| `pong` | `{}` | Heartbeat reply |

`request_id` is client-generated (UUID). The client correlates events without server roundtrips.

## Server Architecture

### File layout

```
app/api/app/
├── api/v1/endpoints/
│   ├── chat.py              # KEEP POST /chat; DELETE POST /chat/stream
│   └── chat_ws.py           # NEW — thin endpoint, ~30 lines
└── services/
    ├── chat_service.py      # EXTEND — accept cancel_event + on_question
    └── chat_ws_session.py   # NEW — per-connection state machine + task supervisor
```

### Component responsibilities

**`chat_ws.py`** — endpoint only. Accepts the WebSocket, constructs `ChatWSSession`, awaits `session.run()`. No business logic.

**`ChatWSSession` (`chat_ws_session.py`)** — one instance per connection. State:

- `websocket: WebSocket`
- `user_id: int | None` (set after auth)
- `current_request_id: str | None`
- `current_task: asyncio.Task | None`
- `cancel_event: asyncio.Event | None`
- `pending_question: asyncio.Future | None` (with associated `request_id`)

Methods:

- `run()` — main loop: read frame → dispatch by `type`
- `_handle_auth`, `_handle_message`, `_handle_cancel`, `_handle_confirm`, `_handle_ping`
- `_spawn_chat_task(request)` — wraps `process_message` with a request-scoped `cancel_event` and `on_question` impl
- `_progress_relay(event)` — receives `on_progress` events from `ChatService`, tags with `request_id`, sends as `progress` event
- `_question_relay(spec)` — builds a future, sends a `question` event, awaits future (with 60s timeout)
- `_send(event)` — JSON send wrapper that swallows `ConnectionClosed`
- `_on_disconnect()` — cancel current task, persist whatever state is appropriate

The session owns the lifecycle of one chat task at a time. On `message` while a task is running: emit `cancelled(reason="superseded")`, await `current_task` (it will resolve from cancellation), then spawn the new task.

**`ChatService.process_message`** — minimal extension. New optional kwargs:

- `cancel_event: asyncio.Event | None` — checked at every function-loop boundary. If set → raise `ChatCancelled` (new exception type).
- `on_question: Callable[[QuestionSpec], Awaitable[Any]] | None` — passed through to tools that opt in. No tool opts in on day one.

`on_progress` callback signature unchanged; supervisor wraps it to tag events with `request_id`.

### Cancellation — two layers, on purpose

1. **`cancel_event.set()`** — cooperative; checked between function-loop iterations inside `process_message`. Clean cancel point between tool calls.
2. **`current_task.cancel()`** — forceful; needed mid-`await` (Firecrawl scrape, Gemini call). Raises `asyncio.CancelledError` in the coroutine.

Supervisor calls both. `process_message` catches `ChatCancelled` (clean) and lets `CancelledError` propagate (forceful). Either way the supervisor's `try/except` around `current_task` lands on the cancel path and emits `cancelled`.

## Data Flow

### Happy path

```
C → S  {auth, token}
S → C  {ready, user_id}
C → S  {message, request_id=r1, text}
S → C  {progress, request_id=r1, step=search_youtube_reviews, status=start}
S → C  {progress, request_id=r1, step=search_youtube_reviews, status=done}
... more progress events ...
S → C  {complete, request_id=r1, data=ChatResponse}
```

### Explicit cancel

```
C → S  {message, request_id=r1, text}
S → C  {progress, request_id=r1, step=ingest_youtube_review, status=start}
C → S  {cancel,  request_id=r1}
       ↳ supervisor: cancel_event.set(); current_task.cancel()
       ↳ ChatService raises ChatCancelled or sees CancelledError
S → C  {cancelled, request_id=r1, reason=user}
```

### Supersede

```
... in-flight r1 ...
C → S  {message, request_id=r2, text}
       ↳ supervisor sees current_task active
S → C  {cancelled, request_id=r1, reason=superseded}
       ↳ supervisor awaits current_task, then spawns r2
S → C  {progress,  request_id=r2, ...}
```

### Interactive question (plumbed, not wired in v1)

```
C → S  {message, request_id=r1, text}
S → C  {question, request_id=r1, prompt, choices}
       ↳ supervisor stores pending_question future
C → S  {confirm,  request_id=r1, answer}
       ↳ future resolves; ChatService resumes
S → C  {complete, request_id=r1, data}
```

Edge cases:

- `confirm` for a non-matching `request_id` → emit `error`, ignore.
- Client disconnects with pending question → future is failed with `ConnectionError`; disconnect handler runs.
- 60s timeout with no `confirm` → future is failed with `QuestionTimeout`; tool falls back to its default behavior.

## Persistence

- **User message** — saved to `messages` table immediately on receive (before spawning the task). A cancelled turn still records the user's input.
- **Assistant message on `complete`** — same as today.
- **Assistant message on `cancelled`** — save row with `role=assistant`, `content=""` (no token streaming in v1, so there is no partial assistant text to preserve), and a new `status` column (`complete | cancelled | error`). Migration adds the column with default `complete` so existing rows remain valid. When token-level streaming lands later, `content` will hold whatever was already streamed at cancel time.
- **`Conversation.last_message_at`** — updates on cancel too (it was a real interaction).

The frontend renders `status=cancelled` rows as greyed-out / "stopped".

## Error Handling, Timeouts, Reconnect

| Condition | Behavior |
|---|---|
| Auth not received within 5s | Close `4401` |
| Idle 5min, no in-flight task | Close `1000` normal |
| Client `ping` | Server `pong`; resets idle timer |
| Question unanswered for 60s | Resolve future with `QuestionTimeout`; tool default fires |
| `ConnectionClosed` during send | Caught; disconnect handler runs |
| Exception in `process_message` (non-cancel) | Emit `error`, mark assistant message `status=error`, keep connection open |
| Client disconnects mid-pipeline | Disconnect handler cancels current task; nothing is "resumed" on reconnect |

**No stream resume.** A reconnecting client uses `GET /api/v1/chat/conversations/{id}` to read whatever was persisted.

## Testing Strategy

### Unit (no uvicorn)

`ChatWSSession` driven by a fake `WebSocket` (queue in / queue out). Cases:

- Auth happy path → `ready` emitted
- Auth timeout → close `4401`
- `message` while idle → spawns task, progress + complete observed
- `cancel` mid-flight → `cancelled(reason=user)`
- `message` while in-flight → `cancelled(reason=superseded)` for old, new task starts
- `confirm` round-trip → future resolves, pipeline continues
- `confirm` for unknown `request_id` → `error` event
- Question timeout → `QuestionTimeout` raised, tool default fires
- Disconnect mid-flight → current_task cancelled, no `complete` sent
- Malformed JSON / unknown `type` → `error` event, connection stays open

`ChatService.process_message` with `cancel_event` set after N function calls → asserts `ChatCancelled` raised at the right boundary.

### Integration (FastAPI `TestClient.websocket_connect`)

- One end-to-end happy path against a stubbed function registry — verifies wiring including DB writes and `complete` shape.
- One end-to-end cancel using a registry stub that sleeps.

Existing review-pipeline tests cover the 7 functions individually — not re-tested here.

## Deletion / Migration

- **Remove** `POST /api/v1/chat/stream` and its `generate()` generator from `app/api/app/api/v1/endpoints/chat.py` in the same PR. No deprecation period — there is no public SDK; the frontend is in-repo.
- **Frontend** converted to WS in the same PR. If frontend changes balloon scope, the contingency split is: PR1 ships the WS endpoint *alongside* the existing SSE endpoint (both alive, no deletion yet); PR2 switches the frontend to WS and deletes SSE. The default plan is single-PR.
- **`POST /api/v1/chat`** stays — non-streaming REST endpoint, used by tests and external callers.
- **`CLAUDE.md`** — update AI Integration section to mention WebSocket transport.

## Agent Reasoning

**Considered and rejected:**

- *`python-socketio`* — buys rooms/acks/auto-reconnect; none are load-bearing for replacing chat streaming. Adds a non-standard protocol the client must understand.
- *Redis pub/sub from day one* — solves horizontal scaling, which we don't have. Doubles design surface (publisher + subscriber + cleanup on disconnect). Refactor target if/when we scale.
- *Query-string token auth* — leaks into nginx logs and browser history. First-message auth keeps it in the frame body.
- *Stream resume on reconnect* — needs a server-side replay buffer keyed by `request_id`, with TTL and ordering guarantees. Significant complexity for a feature that's invisible most of the time. Defer until there's evidence it matters.
- *Wiring `on_question` to a specific tool* (e.g., `search_youtube_reviews` asking which 3 of 12 candidates to deep-analyze) — adds product surface and frontend work that should be evaluated on its own merits. Plumbing ships; behavior change ships in a follow-up.
- *Keeping SSE in parallel* — user explicitly chose "replace". Running both doubles the test matrix without a corresponding win.
- *Wiki-loaded Telnyx/ChompChat context* — appeared in system reminders but belongs to a different project (voice AI on a different stack). No design influence here; called out so future readers don't think this design borrowed from those patterns.

**Decisions left to implementation plan:**

- Exact migration shape for the `messages.status` column (Alembic file content; enum vs string).
- Whether the WS frontend uses native `WebSocket` or a thin wrapper helper with auto-reconnect.
- nginx config snippet for the `/api/v1/chat/ws` location (upgrade headers, no proxy buffering, proxy_read_timeout).
