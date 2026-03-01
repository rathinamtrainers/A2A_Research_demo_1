# Speaker Notes — `async_agent/agent.py`

> **File**: `async_agent/agent.py` (545 lines)
> **Purpose**: Hand-rolled A2A server implementing the full async task lifecycle with push notifications, SSE streaming, and task cancellation.
> **Estimated teaching time**: 35–45 minutes

---

## Why This File Matters

This is the most complex agent in the entire demo, and it is different from
every other agent in a fundamental way. All other agents (weather, research,
code, data) use ADK's `to_a2a()` helper or wrap an `LlmAgent`. The async agent
does **neither** — it is a raw FastAPI application that implements JSON-RPC 2.0
dispatch by hand.

Why? Because the async agent needs fine-grained control over:

- **Task state machines** — moving tasks through `submitted -> working -> completed/canceled/failed`
- **Push notification delivery** — POSTing HMAC-signed webhook payloads with retry logic
- **SSE streaming** — managing per-client event queues and keepalive heartbeats
- **Task cancellation** — propagating `asyncio.Task.cancel()` through to background coroutines

ADK's built-in handler doesn't expose these primitives directly. By going raw,
we get full control — at the cost of more code.

**Key message to students**: "This is what happens under the hood of
`to_a2a()`. Understanding this agent is understanding the A2A protocol at the
wire level."

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–44)

```python
import asyncio
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
```

**Explain to students:**

- `asyncio` is central: background tasks, cancellation, sleep, queues — this
  agent is an asyncio masterclass.
- `httpx` (not `requests`) — async-native HTTP client used for webhook delivery.
  Using `requests` inside an `async def` would block the event loop.
- `hmac` + `hashlib` — for computing HMAC-SHA256 webhook signatures.
- `StreamingResponse` from FastAPI — wraps an async generator into an SSE
  response.
- We import `AgentCard`, `AgentSkill`, and `AgentCapabilities` from the
  `a2a.types` package, but **not** `to_a2a` or `LlmAgent`. This is the
  tell-tale sign that this agent is hand-rolled.

---

### 2. Agent Card (lines 46–75)

```python
_long_task_skill = AgentSkill(
    id="long_running_task",
    name="Long-Running Task",
    description="Executes a simulated long-running task (10–60 seconds)...",
    tags=["async", "long-running", "push-notifications"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

AGENT_CARD = AgentCard(
    name="async_agent",
    url=settings.ASYNC_AGENT_URL,
    capabilities=AgentCapabilities(
        streaming=True,           # F3 — SSE also supported
        push_notifications=True,  # F4 — Webhook push enabled
    ),
    ...
)
```

**Explain to students:**

- The Agent Card is the agent's **advertisement** to the world (F1 — Agent
  Discovery). Clients fetch it from `/.well-known/agent.json`.
- Two capabilities are declared:
  - `streaming=True` (F3): tells clients they can call `message/stream` to get
    SSE events.
  - `push_notifications=True` (F4): tells clients they can register a webhook
    via `tasks/pushNotificationConfig/set` and receive POSTed updates.
- These are not just informational — a well-behaved client checks capabilities
  before calling methods. If `push_notifications` were `False`, the client
  should not attempt to set a webhook config.

**Teaching moment**: Compare this to the other agents' cards. The weather
agent has `streaming=False` and no push capabilities. The Agent Card is a
contract — it tells the client exactly what the agent supports.

---

### 3. In-Memory Stores (lines 77–88)

```python
_task_store: dict[str, dict] = {}        # task_id -> task state dict
_webhook_store: dict[str, dict] = {}     # task_id -> webhook config dict
_running_tasks: dict[str, asyncio.Task] = {}  # task_id -> asyncio.Task
_sse_queues: dict[str, list[asyncio.Queue]] = {}  # task_id -> SSE client queues
```

**Explain to students:**

- Four dictionaries hold the agent's entire world state.
- `_task_store` is the source of truth for task lifecycle. Every JSON-RPC
  handler reads from or writes to this dict.
- `_webhook_store` maps task IDs to their registered webhook configuration
  (URL, optional token). Set via `tasks/pushNotificationConfig/set`.
- `_running_tasks` maps task IDs to live `asyncio.Task` objects. This is
  critical for cancellation — you need a handle to the task to call `.cancel()`.
- `_sse_queues` maps task IDs to **lists** of `asyncio.Queue` objects. Each
  connected SSE client gets its own queue. This is a fan-out pattern — one
  task update gets broadcast to all connected clients.

**Production note**: All four stores are in-memory. In production, you would
replace `_task_store` and `_webhook_store` with Redis or a database.
`_running_tasks` would be replaced by a distributed task queue (Celery, Cloud
Tasks). `_sse_queues` would use Redis Pub/Sub for cross-instance fan-out.

**Teaching moment**: "Why a list of queues per task?" Because multiple clients
can connect to the same task's SSE stream simultaneously (e.g., a dashboard and
a CLI). Each client gets its own queue so they can consume events independently.

---

### 4. FastAPI App and Agent Card Endpoint (lines 91–99)

```python
app = FastAPI(title="async_agent A2A Server")

@app.get("/.well-known/agent.json")
async def get_agent_card() -> dict:
    return AGENT_CARD.model_dump(exclude_none=True)
```

**Explain to students:**

- `/.well-known/agent.json` is the standard A2A discovery path (F1). Any client
  that knows the agent's base URL can discover its capabilities.
- `model_dump(exclude_none=True)` serialises the Pydantic model to a dict,
  omitting any field that is `None`. This keeps the JSON clean.

---

### 5. JSON-RPC 2.0 Dispatch (lines 102–160)

```python
@app.post("/")
async def handle_json_rpc(request: Request) -> JSONResponse:
    body = await request.json()
    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    try:
        if method == "message/send":
            result = await _handle_message_send(params)
        elif method == "message/stream":
            return await _handle_message_stream(rpc_id, params)
        elif method == "tasks/get":
            result = _handle_tasks_get(params)
        elif method == "tasks/cancel":
            result = await _handle_tasks_cancel(params)
        elif method == "tasks/list":
            result = _handle_tasks_list(params)
        elif method == "tasks/pushNotificationConfig/set":
            result = _handle_push_config_set(params)
        elif method == "tasks/pushNotificationConfig/get":
            result = _handle_push_config_get(params)
        else:
            return JSONResponse(content={
                "jsonrpc": "2.0", "id": rpc_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })
    except Exception as exc:
        return JSONResponse(content={
            "jsonrpc": "2.0", "id": rpc_id,
            "error": {"code": -32603, "message": str(exc)},
        })

    return JSONResponse(content={"jsonrpc": "2.0", "id": rpc_id, "result": result})
```

**Explain to students:**

- This is the **heart** of the agent. Every A2A call arrives as a JSON-RPC 2.0
  POST to `/`. The agent reads `method` and dispatches to the right handler.
- Seven methods are supported:
  1. `message/send` — fire-and-forget task creation
  2. `message/stream` — task creation with SSE streaming (F3)
  3. `tasks/get` — poll task status (F5)
  4. `tasks/cancel` — cancel a running task (F5)
  5. `tasks/list` — paginated task listing (F5)
  6. `tasks/pushNotificationConfig/set` — register webhook (F4)
  7. `tasks/pushNotificationConfig/get` — retrieve webhook config (F4)
- **Note the asymmetry**: `message/stream` returns a `StreamingResponse`
  directly (bypasses the normal JSON-RPC envelope), while all other methods
  return a result that gets wrapped in the standard `{"jsonrpc": "2.0", "id": ..., "result": ...}` envelope.
- Error code `-32601` is "Method not found" per the JSON-RPC 2.0 spec.
  Error code `-32603` is "Internal error." These are standard codes, not
  invented.

**Teaching moment**: This dispatch pattern is what `to_a2a()` generates
automatically for other agents. Seeing it spelled out explicitly makes the
protocol tangible.

---

### 6. `_handle_message_send` (lines 165–190)

```python
async def _handle_message_send(params: dict) -> dict:
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "status": {"state": "submitted"},
        "history": [params.get("message", {})],
        "artifacts": [],
    }
    _task_store[task_id] = task
    _running_tasks[task_id] = asyncio.create_task(_execute_long_task(task_id))
    return task
```

**Explain to students:**

- Creates a new task with a UUID, initial state `"submitted"`, the user's
  message in `history`, and an empty `artifacts` list.
- Stores it in `_task_store` so it can be retrieved later via `tasks/get`.
- **`asyncio.create_task()`** is the key line — it schedules `_execute_long_task`
  to run in the background. The HTTP response returns immediately with the
  `submitted` task, while the work continues asynchronously.
- The `asyncio.Task` handle is stored in `_running_tasks` so we can cancel it
  later.

**Teaching moment**: This is the "fire-and-forget" pattern. The client gets
back a task ID immediately and can:
- Poll with `tasks/get` (pull model)
- Register a webhook with `tasks/pushNotificationConfig/set` (push model, F4)
- Connect via `message/stream` for SSE events (streaming model, F3)

---

### 7. `_handle_message_stream` — SSE Streaming (lines 193–269)

```python
async def _handle_message_stream(rpc_id: Any, params: dict) -> StreamingResponse:
    # ... create task (same as message/send) ...

    queue: asyncio.Queue = asyncio.Queue()
    _sse_queues.setdefault(task_id, []).append(queue)

    _running_tasks[task_id] = asyncio.create_task(_execute_long_task(task_id))

    async def _event_generator():
        # Yield initial "submitted" event
        yield f"data: {json.dumps(initial_event)}\n\n"

        terminal_states = {"completed", "failed", "canceled"}
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                yield f"data: {json.dumps(event)}\n\n"

                state = event.get("result", {}).get("status", {}).get("state", "")
                if state in terminal_states:
                    break
        finally:
            queues = _sse_queues.get(task_id, [])
            if queue in queues:
                queues.remove(queue)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**This is the most complex handler. Walk through it carefully:**

1. **Queue creation** (line 219): Each SSE client gets a dedicated
   `asyncio.Queue`. When `_execute_long_task` updates the task, it broadcasts
   to all queues via `_emit_sse_event`.

2. **`_event_generator`** — an async generator that yields SSE-formatted lines:
   - First, the initial `submitted` event
   - Then a loop that pulls events from the queue
   - **Keepalive** (line 247): If no event arrives within 60 seconds, we yield
     an SSE comment (`: keepalive\n\n`). This prevents proxies/load balancers
     from closing the connection due to inactivity.
   - **Terminal state check**: Once the task reaches `completed`, `failed`, or
     `canceled`, the generator exits.

3. **Cleanup** (lines 256–259): The `finally` block removes the queue from
   `_sse_queues`. Without this, dead queues would accumulate and waste memory.

4. **Response headers**:
   - `Cache-Control: no-cache` — prevents caching of the SSE stream.
   - `X-Accel-Buffering: no` — tells Nginx (if present) not to buffer the
     response. Without this, Nginx would buffer events and deliver them all at
     once when the stream ends, defeating the purpose of SSE.

**Teaching moment**: SSE is a unidirectional protocol — server pushes to client
over a single HTTP connection. It is simpler than WebSockets but cannot receive
data from the client. For A2A's use case (progress updates), SSE is ideal.

---

### 8. `_handle_tasks_get` (lines 272–288)

```python
def _handle_tasks_get(params: dict) -> dict:
    task_id = params.get("id")
    if not task_id or task_id not in _task_store:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return _task_store[task_id]
```

**Explain to students:**

- The simplest handler — just a lookup in `_task_store`.
- This is the "pull" model of task tracking: clients poll this method
  periodically to check if the task is done.
- Note it is a synchronous function (no `async`), since there is no I/O.

---

### 9. `_handle_tasks_cancel` (lines 291–311)

```python
async def _handle_tasks_cancel(params: dict) -> dict:
    task_id = params.get("id")
    if not task_id or task_id not in _task_store:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task_id in _running_tasks:
        _running_tasks[task_id].cancel()
        del _running_tasks[task_id]

    _task_store[task_id]["status"] = {"state": "canceled"}
    return _task_store[task_id]
```

**Explain to students:**

- Cancellation is a two-step process:
  1. Call `.cancel()` on the `asyncio.Task` — this injects a `CancelledError`
     into the running coroutine at the next `await` point.
  2. Update `_task_store` to reflect the `canceled` state.
- The `del _running_tasks[task_id]` prevents double-cancellation.
- In `_execute_long_task`, the `except asyncio.CancelledError` block catches
  this and sends a final push notification and SSE event.

**Teaching moment**: `asyncio.Task.cancel()` is **cooperative** cancellation,
not preemptive. The coroutine will only see the `CancelledError` when it next
`await`s something (e.g., `asyncio.sleep`). If the coroutine is doing blocking
CPU work without any `await`, cancellation will not take effect until it yields
control.

---

### 10. `_handle_tasks_list` — Cursor-Based Pagination (lines 314–348)

```python
def _handle_tasks_list(params: dict) -> dict:
    cursor = params.get("cursor")
    page_size = int(params.get("page_size", 20))
    page_size = max(1, min(page_size, 100))  # clamp to [1, 100]

    all_ids = list(_task_store.keys())

    start_idx = 0
    if cursor and cursor in _task_store:
        try:
            start_idx = all_ids.index(cursor) + 1
        except ValueError:
            start_idx = 0

    page = all_ids[start_idx : start_idx + page_size]
    tasks = [_task_store[tid] for tid in page]
    next_cursor = page[-1] if len(page) == page_size else None

    return {"tasks": tasks, "next_cursor": next_cursor, "total_count": len(all_ids)}
```

**Explain to students:**

- **Cursor-based pagination** is preferred over offset-based pagination for
  mutable collections. With offset-based, inserting or deleting items between
  pages causes items to be skipped or duplicated. With cursor-based, you always
  resume from a stable reference point.
- `page_size` is clamped to `[1, 100]` to prevent abuse (e.g., requesting
  page_size=1000000).
- The cursor is the **last task ID** on the current page. The next page starts
  at the task after the cursor.
- `next_cursor` is `None` when there are no more pages (fewer results than
  `page_size`).

**Limitation to note**: This implementation uses insertion-order of Python
dicts (guaranteed since Python 3.7). In production with a database, you would
use a monotonically increasing ID or timestamp as the cursor.

---

### 11. Push Notification Config Handlers (lines 351–382)

```python
def _handle_push_config_set(params: dict) -> dict:
    task_id = params.get("taskId")
    config = params.get("pushNotificationConfig", {})
    if not task_id or not config.get("url"):
        raise ValueError("taskId and pushNotificationConfig.url are required")
    _webhook_store[task_id] = config
    return {"taskId": task_id, "pushNotificationConfig": config}

def _handle_push_config_get(params: dict) -> dict:
    task_id = params.get("taskId")
    config = _webhook_store.get(task_id or "", {})
    return {"taskId": task_id, "pushNotificationConfig": config}
```

**Explain to students:**

- These methods let the client register a webhook URL **per task** (F4).
- The config includes a `url` (where to POST updates) and an optional `token`
  (added as a `Bearer` token in the `Authorization` header).
- The `set` handler validates that both `taskId` and `url` are present.
- The `get` handler returns an empty dict if no config is registered — it
  does not error.

**Teaching moment**: Push notification config is registered **after** the task
is created. The typical flow is:
1. Client calls `message/send` and gets back a task ID.
2. Client calls `tasks/pushNotificationConfig/set` with that task ID and a
   webhook URL.
3. The agent starts POSTing updates to the webhook as the task progresses.

---

### 12. `_compute_webhook_signature` — HMAC-SHA256 (lines 385–405)

```python
def _compute_webhook_signature(body_bytes: bytes) -> str:
    sig = hmac.new(
        settings.WEBHOOK_AUTH_TOKEN.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"
```

**Explain to students:**

- This is the same pattern GitHub uses for webhook signatures.
- The shared secret (`WEBHOOK_AUTH_TOKEN` from `shared/config.py`) is used as
  the HMAC key. The entire JSON body is the message.
- The result is formatted as `sha256=<hex>` and sent in the
  `X-Webhook-Signature` header.
- The receiver recomputes the HMAC and uses `hmac.compare_digest()` for
  constant-time comparison (see `shared/auth.py`).

**Teaching moment**: HMAC provides **integrity** (body was not tampered with)
and **authenticity** (sender knows the secret). It does NOT provide
**confidentiality** (the body is not encrypted). Use HTTPS for that.

---

### 13. `_execute_long_task` — Background Task Simulation (lines 410–465)

```python
async def _execute_long_task(task_id: str) -> None:
    total_duration = 20  # seconds
    steps = 4
    step_duration = total_duration / steps

    try:
        _task_store[task_id]["status"] = {"state": "working"}
        await _push_notification(task_id, "working", progress=0)
        await _emit_sse_event(task_id, "working", progress=0, final=False)

        for step in range(1, steps + 1):
            await asyncio.sleep(step_duration)
            progress = int((step / steps) * 100)

            if step < steps:
                # Intermediate progress update
                _task_store[task_id]["status"] = {
                    "state": "working", "message": f"Progress: {progress}%",
                }
                await _push_notification(task_id, "working", progress=progress)
                await _emit_sse_event(task_id, "working", progress=progress, final=False)
            else:
                # Final step — create artifact, mark completed
                result_artifact = { ... }
                _task_store[task_id]["artifacts"].append(result_artifact)
                _task_store[task_id]["status"] = {"state": "completed"}
                await _push_notification(task_id, "completed", progress=100)
                await _emit_sse_event(task_id, "completed", progress=100, final=True)

    except asyncio.CancelledError:
        _task_store[task_id]["status"] = {"state": "canceled"}
        await _push_notification(task_id, "canceled", progress=-1)
        await _emit_sse_event(task_id, "canceled", progress=-1, final=True)
    except Exception as exc:
        _task_store[task_id]["status"] = {"state": "failed", "message": str(exc)}
        await _push_notification(task_id, "failed", progress=-1)
        await _emit_sse_event(task_id, "failed", progress=-1, final=True)
    finally:
        _running_tasks.pop(task_id, None)
```

**Walk through the lifecycle step by step:**

1. **Transition to `working`** (line 425): The task moves out of `submitted`
   immediately. Both push notification and SSE event are emitted.

2. **Progress loop** (lines 429–454): Four iterations, 5 seconds each (20
   seconds total). At each step:
   - Sleep simulates real work.
   - Progress is reported at 25%, 50%, 75%, 100%.
   - Each update is triple-stored: in `_task_store` (for polling), via
     `_push_notification` (for webhooks), and via `_emit_sse_event` (for SSE
     clients).

3. **Completion** (lines 441–454): On the final step, an artifact is created
   and the task is marked `completed`.

4. **Cancellation** (lines 456–459): If `asyncio.CancelledError` is raised
   (from `_handle_tasks_cancel`), the task transitions to `canceled`. The agent
   still sends a push notification and SSE event so clients know the task ended.

5. **Failure** (lines 460–463): Any other exception marks the task as `failed`.

6. **Cleanup** (line 465): The `finally` block removes the task from
   `_running_tasks` regardless of outcome.

**Teaching moment**: Notice the full A2A task state machine in action:
```
submitted -> working -> completed
                     -> canceled  (via CancelledError)
                     -> failed    (via Exception)
```
This matches the A2A protocol specification for task lifecycle states.

---

### 14. `_emit_sse_event` — Broadcasting to SSE Clients (lines 468–495)

```python
async def _emit_sse_event(
    task_id: str, state: str, progress: int, final: bool
) -> None:
    queues = _sse_queues.get(task_id, [])
    if not queues:
        return

    event = {
        "jsonrpc": "2.0", "id": None,
        "result": {
            "id": task_id,
            "event": "TaskStatusUpdateEvent",
            "status": {"state": state, "progress": progress},
            "final": final,
        },
    }
    for q in list(queues):
        await q.put(event)
```

**Explain to students:**

- This is the **fan-out** mechanism. The event is put into every queue in the
  list, so every connected SSE client receives it.
- `list(queues)` creates a copy of the list before iterating. This is important
  because the `_event_generator` in `_handle_message_stream` may remove a queue
  from the list (in its `finally` block) during iteration.
- If no SSE clients are connected (`not queues`), the function returns
  immediately — no wasted work.
- The `final` flag tells the SSE client whether this is the last event for
  this task.

---

### 15. `_push_notification` — Webhook Delivery with Retry (lines 498–545)

```python
async def _push_notification(task_id: str, state: str, progress: int) -> None:
    config = _webhook_store.get(task_id)
    if not config or not config.get("url"):
        return  # No webhook registered

    payload = {
        "event": "TaskStatusUpdateEvent",
        "taskId": task_id,
        "status": {"state": state, "progress": progress},
    }
    body_bytes = json.dumps(payload).encode()

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": _compute_webhook_signature(body_bytes),
    }
    if config.get("token"):
        headers["Authorization"] = f"Bearer {config['token']}"

    max_retries = 3
    delay = 1.0

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    config["url"], content=body_bytes, headers=headers
                )
                response.raise_for_status()
                return  # Success
        except (httpx.RequestError, httpx.HTTPStatusError):
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            # On final attempt, give up silently
```

**Walk through the key details:**

1. **Early return** (line 512): If no webhook is registered for this task, do
   nothing. Push notifications are opt-in.

2. **HMAC signature** (line 524): Every webhook delivery includes an
   `X-Webhook-Signature` header so the receiver can verify authenticity.

3. **Optional Bearer token** (lines 526–527): If the client provided a `token`
   in the push notification config, it is included as an `Authorization` header.

4. **Retry with exponential backoff** (lines 529–544):
   - 3 attempts total
   - Initial delay: 1 second, then 2 seconds, then 4 seconds
   - Both network errors (`RequestError`) and HTTP errors (`HTTPStatusError`)
     trigger retries
   - On the final attempt, the failure is swallowed silently

**Teaching moment**: Exponential backoff is critical for webhook delivery.
Without it, a temporarily-down receiver would be hammered with rapid retries,
making recovery harder. The doubling pattern (1s, 2s, 4s) is the standard
approach.

**Production improvements to discuss:**
- Add jitter to the backoff (randomize delay slightly) to prevent thundering
  herd when many webhooks retry simultaneously.
- Use a dead-letter queue for permanently failed deliveries.
- Add structured logging for retry attempts and failures.
- Reuse the `httpx.AsyncClient` across calls instead of creating a new one
  per delivery (connection pooling).

---

## Design Patterns to Highlight

1. **Hand-Rolled Protocol Server**: Building the JSON-RPC dispatcher manually
   gives full control over the request/response lifecycle. This is the escape
   hatch when framework abstractions (like `to_a2a()`) are too opinionated.

2. **Fire-and-Forget with `asyncio.create_task()`**: The HTTP response returns
   immediately; real work runs in the background. This is the fundamental
   pattern for long-running tasks in async Python.

3. **Fan-Out via Queues**: Each SSE client gets a dedicated `asyncio.Queue`.
   The producer (background task) writes to all queues; each consumer (SSE
   connection) reads from its own. This cleanly decouples producers from
   consumers.

4. **Cooperative Cancellation**: `asyncio.Task.cancel()` injects a
   `CancelledError` at the next `await` point. The coroutine catches it and
   performs cleanup — this is not preemptive killing.

5. **Exponential Backoff Retry**: Webhook delivery retries with doubling
   delays. This is industry-standard for unreliable outbound webhooks.

6. **Cursor-Based Pagination**: `tasks/list` uses the last task ID as a cursor
   rather than a numeric offset. This is stable under concurrent insertions.

7. **HMAC Webhook Signatures**: Every outgoing webhook is signed with
   HMAC-SHA256. This is the same pattern used by GitHub, Stripe, and Slack.

---

## Common Student Questions

1. **"Why not use `to_a2a()` like the other agents?"** Because `to_a2a()`
   wraps an `LlmAgent` and handles the JSON-RPC dispatch internally. The async
   agent needs to manage task state, background execution, SSE streams, and
   webhook delivery — none of which are exposed by `to_a2a()`. Going raw is the
   only way to get this level of control.

2. **"What happens if the server restarts mid-task?"** All in-memory state is
   lost. Tasks, webhook configs, running coroutines — everything disappears.
   In production, you would persist task state to a database and use a durable
   task queue (Celery, Cloud Tasks, Pub/Sub) so tasks survive restarts.

3. **"Can multiple clients stream the same task?"** Yes. Each
   `message/stream` call creates its own queue in `_sse_queues[task_id]`.
   All queues receive the same events. This is the fan-out pattern.

4. **"Why does the keepalive use `: keepalive` instead of `data: keepalive`?"**
   In the SSE spec, lines starting with `:` are comments — the browser/client
   ignores them. They exist solely to keep the TCP connection alive through
   proxies that close idle connections. Using `data:` would deliver an actual
   event to the client, which is not what we want.

5. **"Why does `_push_notification` fail silently on the last retry?"** This is
   a pragmatic choice for a demo. In production, you would log the failure,
   emit a metric, and possibly write to a dead-letter queue for manual
   investigation. But crashing the background task because a webhook is
   unreachable would be worse — the task itself should still complete.

6. **"Why create a new `httpx.AsyncClient` per webhook delivery?"** Simplicity.
   In production, you would create a single client at module level and reuse it
   for connection pooling. Creating a new client per request means a new TCP
   connection each time, which adds latency.

7. **"How does cancellation actually propagate?"** When `_handle_tasks_cancel`
   calls `_running_tasks[task_id].cancel()`, Python injects a `CancelledError`
   into `_execute_long_task` at the next `await asyncio.sleep(step_duration)`.
   The `except asyncio.CancelledError` block catches it, updates the store,
   and emits final notifications.

---

## Related Files

- `shared/config.py` — Source of `settings.ASYNC_AGENT_URL` and
  `settings.WEBHOOK_AUTH_TOKEN`
- `shared/auth.py` — `verify_webhook_signature()` is the receiver-side
  counterpart to `_compute_webhook_signature()`
- `webhook_server/main.py` — The webhook receiver that validates HMAC
  signatures and logs push notification deliveries
- `clients/a2a_client.py` — Client-side code that calls `message/send`,
  `message/stream`, `tasks/get`, `tasks/cancel`, and push notification config
  methods
- `orchestrator_agent/agent.py` — May delegate to async_agent via
  `RemoteA2aAgent` using the Agent Card URL
- `tests/` — Tests for task lifecycle, SSE streaming, push notifications, and
  cancellation
