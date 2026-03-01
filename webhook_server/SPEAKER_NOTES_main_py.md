# Speaker Notes — `webhook_server/main.py`

> **File**: `webhook_server/main.py` (256 lines)
> **Purpose**: FastAPI server that receives, verifies, stores, and displays A2A push notification deliveries.
> **Estimated teaching time**: 15–20 minutes

---

## Why This File Matters

The A2A Protocol defines push notifications (Feature F4) as the mechanism for
agents to proactively deliver task updates to interested parties. This file is
the **receiving end** of that pipeline. Without a webhook server, there is
nowhere for async_agent's push notifications to land — they would fire into
the void.

This is also the only server in the project that is **not** an A2A agent
itself. It is a plain FastAPI application that acts as a notification
consumer. This distinction is worth highlighting: the A2A ecosystem includes
both agents (producers of work) and infrastructure services (consumers of
events).

```
async_agent (port 8005)
   │
   │  POST /webhook
   │  X-Webhook-Signature: sha256=<hex>
   │  Body: { taskId, status, ... }
   │
   ▼
webhook_server (port 9000)   ← this file
   │
   ├── Verify HMAC signature
   ├── Add receipt timestamp
   ├── Store in-memory (_event_log)
   ├── Persist to JSONL file
   └── Pretty-print to console
```

---

## Section-by-Section Walkthrough

### 1. Imports and Module-Level Setup (lines 1–34)

```python
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from rich.console import Console
from rich.panel import Panel

from shared.auth import verify_webhook_signature
from shared.config import settings

console = Console()

app = FastAPI(
    title="A2A Webhook Receiver",
    description="Receives push notification deliveries from A2A agents.",
    version="1.0.0",
)
```

**Explain to students:**

- The server imports `verify_webhook_signature` from `shared.auth` — this is
  the HMAC-SHA256 verification function covered in the auth module notes.
- `Rich` is used purely for demo visibility. The `Console` and `Panel` objects
  produce coloured, boxed output in the terminal so the instructor can show
  events arriving in real time during a live demo.
- `settings` is imported but not directly used in this file's routes — the
  auth verification function reads `settings.WEBHOOK_AUTH_TOKEN` internally.

---

### 2. In-Memory Event Store (lines 42–44)

```python
_event_log: dict[str, list[dict]] = defaultdict(list)
```

**Explain to students:**

- `_event_log` maps `task_id` to a list of events received for that task,
  in arrival order.
- `defaultdict(list)` means accessing a missing key auto-creates an empty
  list — no need to check `if task_id not in _event_log` before appending.
- The leading underscore signals this is a module-private variable, not part
  of the public API. External code should interact via the HTTP routes.

**Teaching moment**: This is a simple but effective pattern for event
sourcing. The in-memory store gives fast reads, and the JSONL file (next
section) provides durability. In production, you would replace this with a
proper event store (Redis Streams, Apache Kafka, or a database table with
an append-only insert pattern).

---

### 3. JSONL Persistence (lines 46–95)

```python
_EVENTS_FILE: Path = Path(
    os.environ.get("WEBHOOK_EVENTS_FILE", "/tmp/webhook_events.jsonl")
)
```

#### 3a. `_persist_event()` (lines 53–67)

```python
def _persist_event(event: dict) -> None:
    try:
        with _EVENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass  # Non-fatal — in-memory store remains the source of truth
```

**Explain to students:**

- Opens the file in **append mode** (`"a"`) — this is critical. Append mode
  guarantees that concurrent writes do not overwrite each other (on POSIX
  systems, append writes are atomic up to `PIPE_BUF` size, typically 4096
  bytes).
- Each event is serialized as a single JSON line followed by a newline. This
  is the **JSONL (JSON Lines)** format.
- The `OSError` catch makes persistence **non-fatal**. If the file is on a
  read-only filesystem or the disk is full, the server continues operating
  with in-memory storage only. This is a deliberate design choice: webhook
  receipt should never fail because of a persistence issue.

**Teaching moment — why JSONL over a single JSON array?**

- A JSON array (`[{...}, {...}, ...]`) requires reading and rewriting the
  entire file for every append — you need to strip the closing `]`, add a
  comma and the new object, then add `]` back.
- JSONL is append-only: just write one line. If the process crashes mid-write,
  only the last (incomplete) line is corrupted — all previous lines remain
  valid.
- Each line is independently parseable, making JSONL ideal for streaming
  processing, `grep`, and partial reads.
- This is the same format used by OpenAI batch API results, structured
  logging (e.g., JSON-formatted log output), and many data pipeline tools.

#### 3b. `_load_persisted_events()` (lines 70–95)

```python
def _load_persisted_events() -> None:
    if not _EVENTS_FILE.exists():
        return
    try:
        with _EVENTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        event = json.loads(line)
                        task_id = event.get("taskId", "unknown")
                        _event_log[task_id].append(event)
                    except json.JSONDecodeError:
                        pass  # Skip malformed lines
    except OSError:
        pass
```

**Explain to students:**

- Called at **module import time** (line 95), before any requests arrive.
  This means a server restart automatically replays all previously received
  events into the in-memory store.
- The double-`try` structure is intentional: the outer `try` catches file-level
  errors (missing file, permission denied), the inner `try` catches
  line-level parse errors (malformed JSON from a partial write or corruption).
- `json.JSONDecodeError` for individual lines means one bad line does not
  prevent loading the rest of the file — **graceful degradation**.
- `event.get("taskId", "unknown")` handles events that lack a `taskId` field
  (defensive coding against unexpected payloads).

**Teaching moment**: This is the **event replay** pattern. By persisting events
as they arrive and replaying them on startup, the server achieves eventual
consistency across restarts without needing a database. This pattern is
foundational to event sourcing architectures.

---

### 4. Health Check Route (lines 100–107)

```python
@app.get("/")
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": "a2a-webhook-receiver",
        "events_received": sum(len(v) for v in _event_log.values()),
    }
```

**Explain to students:**

- Returns the total event count across all tasks. This is useful for
  quick verification that events are flowing during a demo.
- The `"service"` field identifies the server in logs and monitoring
  dashboards — especially useful when multiple services run behind a
  load balancer.
- Health checks are a standard pattern for container orchestrators
  (Kubernetes liveness probes, Cloud Run health checks).

---

### 5. Webhook Receive Route — the Core Endpoint (lines 110–158)

```python
@app.post("/webhook")
async def receive_webhook(request: Request) -> JSONResponse:
    body_bytes = await request.body()

    # Verify HMAC signature if present (optional for local dev)
    sig_header = request.headers.get("X-Webhook-Signature", "")
    if sig_header:
        if not verify_webhook_signature(body_bytes, sig_header):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    try:
        event: dict[str, Any] = json.loads(body_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {exc}",
        ) from exc

    # Store event with receipt timestamp
    task_id = event.get("taskId", "unknown")
    event["_received_at"] = datetime.now(timezone.utc).isoformat()
    _event_log[task_id].append(event)

    # Persist event to JSONL file for replay
    _persist_event(event)

    # Log to console for demo visibility
    _log_event(event)

    return JSONResponse(content={"accepted": True}, status_code=status.HTTP_200_OK)
```

This is the most important function in the file. Walk through it step by step:

**Step 1 — Read raw body:**

- `await request.body()` reads the raw bytes. We need the raw bytes (not
  parsed JSON) because HMAC verification must run on the **exact bytes** the
  sender signed. Parsing to JSON and re-serializing could change key ordering,
  whitespace, or encoding — invalidating the signature.

**Step 2 — HMAC signature verification:**

- `request.headers.get("X-Webhook-Signature", "")` — note the default of
  empty string, not `None`. This avoids a `TypeError` if the header is absent.
- **The conditional `if sig_header:`** is the key design decision. When the
  header is absent, the server accepts the event without verification. This
  makes local development easier (no need to configure signing), but it means
  **signature verification is opt-in, not mandatory**.

**Key teaching moment — local dev vs. production:**

> "In local development, we skip signature verification so you can `curl`
> events directly at the webhook server for testing. In production, you would
> make verification mandatory — remove the `if sig_header:` guard and always
> verify. An unsigned webhook in production is a security vulnerability:
> anyone who discovers the endpoint URL can inject fake events."

**Step 3 — Parse JSON:**

- Wraps `json.loads()` in a try/except and returns a clean 400 error with the
  decode error message. This gives the sender actionable feedback.

**Step 4 — Enrich and store:**

- `event["_received_at"]` adds a server-side receipt timestamp. The leading
  underscore convention signals this field was added by the receiver, not the
  sender. This is useful for measuring delivery latency (compare `_received_at`
  with any sender-side timestamp in the event).
- `datetime.now(timezone.utc)` — always use UTC for server-side timestamps.
  Never use `datetime.now()` without a timezone (it returns local time, which
  is ambiguous and non-portable).

**Step 5 — Persist and log:**

- Persist before logging: if logging fails (e.g., Rich rendering error),
  the event is still saved to disk.
- `_log_event()` produces the colourful console output the instructor shows
  during live demos.

---

### 6. Query Routes (lines 161–215)

#### 6a. `GET /events` — All Events (lines 161–169)

```python
@app.get("/events")
async def list_all_events() -> dict:
    return dict(_event_log)
```

- Converts `defaultdict` to a regular `dict` for JSON serialization. This
  prevents the response from including the `defaultdict` type information.
- Returns events grouped by `task_id` — useful for seeing the full picture.

#### 6b. `GET /events/{task_id}/latest` — Most Recent Event (lines 172–192)

```python
@app.get("/events/{task_id}/latest")
async def get_task_latest_event(task_id: str) -> dict:
    events = _event_log.get(task_id)
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No events found for task: {task_id}",
        )
    return {"task_id": task_id, "event": events[-1]}
```

**Explain to students:**

- `events[-1]` returns the last element — the most recent event for this task.
- This route is registered **before** `GET /events/{task_id}` (line 195). This
  matters for FastAPI route ordering: `/events/{task_id}/latest` must come
  first, otherwise `latest` would be captured as a `task_id` value by the
  `{task_id}` path parameter.

**Teaching moment**: FastAPI matches routes in registration order. If
`/events/{task_id}` were registered first, a request to `/events/abc/latest`
would match with `task_id="abc"` and the `/latest` suffix would cause a
404 or routing error. Always register more specific routes before less
specific ones.

#### 6c. `GET /events/{task_id}` — All Events for a Task (lines 195–215)

```python
@app.get("/events/{task_id}")
async def get_task_events(task_id: str) -> dict:
    events = _event_log.get(task_id)
    if events is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No events found for task: {task_id}",
        )
    return {"task_id": task_id, "events": events}
```

- Note the subtle difference: `if events is None` vs. `if not events` in the
  `/latest` route. Both work here because `_event_log` is a `defaultdict` —
  accessing a missing key creates an empty list, so `.get()` is used to avoid
  that side effect. `is None` is more precise: it distinguishes "key not
  found" from "key exists but list is empty."

---

### 7. Delete Route — Testing Reset (lines 218–228)

```python
@app.delete("/events")
async def clear_events() -> dict:
    count = sum(len(v) for v in _event_log.values())
    _event_log.clear()
    try:
        _EVENTS_FILE.write_text("")
    except OSError:
        pass
    return {"cleared": count}
```

**Explain to students:**

- Clears both the in-memory store **and** truncates the persistence file.
  If you only cleared the in-memory store, restarting the server would reload
  the old events from disk.
- `_EVENTS_FILE.write_text("")` truncates (empties) the file rather than
  deleting it. This avoids file-not-found edge cases on subsequent writes.
- Returns the count of cleared events so the caller knows something happened.
- This endpoint is for testing and demo resets only — it would not exist in
  a production deployment.

---

### 8. Console Logging Helper (lines 233–250)

```python
def _log_event(event: dict) -> None:
    task_id = event.get("taskId", "?")
    state = event.get("status", {}).get("state", "?")
    progress = event.get("status", {}).get("progress", "?")
    received_at = event.get("_received_at", "?")

    console.print(
        Panel(
            f"[bold cyan]PUSH NOTIFICATION RECEIVED[/bold cyan]\n"
            f"  Task ID  : {task_id}\n"
            f"  State    : [yellow]{state}[/yellow]\n"
            f"  Progress : {progress}%\n"
            f"  Received : {received_at}",
            title="[dim]webhook_server[/dim]",
            border_style="green",
        )
    )
```

**Explain to students:**

- `Rich` markup (`[bold cyan]`, `[yellow]`) provides syntax highlighting in
  the terminal. This makes live demos visually clear — the instructor can
  point at the terminal and say "see, the push notification just arrived."
- Chained `.get()` calls with defaults (`event.get("status", {}).get("state", "?")`)
  prevent `KeyError` / `TypeError` on unexpected event shapes. Defensive
  coding at its most practical.
- This function is purely for demo purposes. In production, you would use
  structured logging (e.g., `structlog` or Python's `logging` module with
  JSON formatters).

---

### 9. Direct Execution Guard (lines 253–256)

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
```

**Explain to students:**

- Allows running the server directly with `python -m webhook_server.main`
  as an alternative to `uvicorn webhook_server.main:app --port 9000`.
- `host="0.0.0.0"` binds to all interfaces — necessary for Docker containers
  where `localhost` would be unreachable from outside the container.
- Port 9000 is the conventional port for the webhook server in this project
  (see `shared/config.py` → `WEBHOOK_SERVER_URL`).

---

## Design Patterns to Highlight

1. **Event Sourcing (Lightweight)**: Events are the source of truth. The
   in-memory store is a derived view that can be rebuilt from the JSONL file
   at any time. This is the same principle behind Kafka consumers, Redux
   stores, and CQRS architectures.

2. **Append-Only Log (JSONL)**: Write-once, read-many. Each line is
   independent. Survives partial writes and process crashes. No locking
   required for concurrent appends (POSIX atomicity guarantee for small
   writes).

3. **Graceful Degradation**: Persistence failures are caught and swallowed.
   The server continues operating with in-memory storage. This is preferable
   to crashing on a disk error when the primary function (receiving webhooks)
   can still succeed.

4. **Defense in Depth (Conditional)**: HMAC verification is present but
   optional. The code is structured so that enabling mandatory verification
   requires removing one `if` guard — a minimal change for production
   hardening.

5. **Enrichment at Ingestion**: Adding `_received_at` at receipt time creates
   an audit trail. The underscore prefix convention distinguishes
   server-added metadata from the original event payload.

---

## Common Student Questions

1. **"Why is HMAC verification optional?"** For developer ergonomics. During
   local development, you want to be able to `curl -X POST` test events at
   the webhook endpoint without computing HMAC signatures by hand. In
   production, you would remove the `if sig_header:` guard and always verify.
   The code comment on line 130 makes this explicit.

2. **"What happens if two events arrive at the same time?"** FastAPI (via
   uvicorn) handles requests concurrently using async coroutines. Since
   `_event_log` is a plain `dict` and Python's GIL protects dict operations,
   concurrent appends are safe in a single-process deployment. For
   multi-process deployments (e.g., gunicorn with multiple workers), you would
   need a shared store like Redis.

3. **"Why not use a database instead of JSONL?"** For a demo, JSONL is
   zero-dependency and transparent — you can `cat` or `grep` the file
   directly. A database (SQLite, PostgreSQL) would be appropriate for
   production but adds setup complexity that distracts from the A2A protocol
   concepts being taught.

4. **"Why does the server return `{"accepted": True}` instead of the stored
   event?"** Following the webhook receiver convention (used by GitHub,
   Stripe, Slack): acknowledge receipt quickly with a minimal response. The
   sender does not need the enriched event back — it already has the original
   payload. Minimal responses also reduce bandwidth and latency.

5. **"Could this server miss events if it restarts?"** Yes, briefly. Events
   arriving during the restart window (process down) will receive connection
   errors. The sending agent (async_agent) should implement retry logic with
   exponential backoff. The A2A protocol does not mandate delivery guarantees
   — that is left to the implementation. This is analogous to HTTP webhook
   delivery in services like GitHub or Stripe, which retry failed deliveries.

---

## Related Files

- `shared/auth.py` — Provides `verify_webhook_signature()` (HMAC-SHA256
  verification using `settings.WEBHOOK_AUTH_TOKEN`)
- `shared/config.py` — Defines `WEBHOOK_SERVER_URL` (default `http://localhost:9000`)
  and `WEBHOOK_AUTH_TOKEN` (the shared HMAC secret)
- `async_agent/agent.py` — The sender: registers the webhook URL via
  `tasks/pushNotificationConfig/set` and POSTs signed events to `/webhook`
- `tests/test_webhook_server.py` — Tests for all routes including HMAC
  verification, event storage, and JSONL persistence
- `clients/a2a_client.py` — Client that triggers async tasks which
  ultimately produce push notification deliveries to this server
