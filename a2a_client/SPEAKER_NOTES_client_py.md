# Speaker Notes — `a2a_client/client.py`

> **File**: `a2a_client/client.py` (286 lines)
> **Purpose**: Standalone A2A HTTP client proving cross-framework interoperability without any ADK or a2a-sdk client dependency.
> **Estimated teaching time**: 20–25 minutes

---

## Why This File Matters

This is the **interoperability proof** of the entire demo. Every other module
in this project uses Google ADK, the a2a-sdk, or both. This client uses
**only httpx** — a plain HTTP library. It constructs JSON-RPC 2.0 payloads by
hand, parses SSE streams manually, and talks to any A2A-compliant agent.

The teaching message is powerful:

> "If your agent speaks the A2A protocol, *any* HTTP client in *any* language
> can talk to it. No SDK lock-in. No framework coupling. This file proves it."

This is Feature F24 — Cross-Framework Interoperability — in its purest form.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–38)

```python
import httpx
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

from shared.config import settings
```

**Explain to students:**

- The import list is deliberately minimal: `httpx` for HTTP, `json` and `uuid`
  from the standard library, and `rich` for pretty console output. There is no
  `from a2a_sdk import ...`, no `from google.adk import ...`.
- `httpx` is the async-capable successor to `requests`. It supports
  `async with client.stream(...)` which is essential for SSE.
- The only project dependency is `shared.config.settings` for the agent URL.
  The client itself is framework-agnostic.

**Teaching moment**: Count the imports. Compare this file to an agent file
that imports ADK, a2a-sdk, FastAPI, etc. The contrast shows the protocol's
value — the consumer side is trivially simple.

---

### 2. `A2ADemoClient.__init__` (lines 41–66)

```python
class A2ADemoClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["X-API-Key"] = api_key
        if bearer_token:
            self._headers["Authorization"] = f"Bearer {bearer_token}"
```

**Explain to students:**

- The constructor accepts `base_url` plus two optional auth parameters. This
  mirrors the A2A spec's `securitySchemes`: API Key (`X-API-Key` header) and
  Bearer token (`Authorization: Bearer ...`).
- `base_url.rstrip("/")` normalizes trailing slashes so we can safely append
  paths like `/.well-known/agent.json` without double slashes.
- Headers are built once at construction time and reused for every request.
  This is a simple but effective pattern for keeping auth logic out of
  individual methods.

**Teaching moment**: This is the **client-side counterpart** to the auth
functions in `shared/auth.py`. The server verifies; the client attaches.
Students can trace the complete auth flow across both files.

---

### 3. `fetch_agent_card()` — Agent Discovery (lines 67–83, Feature F1)

```python
async def fetch_agent_card(self) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{self.base_url}/.well-known/agent.json",
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()
```

**Explain to students:**

- This is A2A Feature F1 — Agent Card Discovery. The well-known URI
  `/.well-known/agent.json` is defined by the A2A spec, following the same
  convention as `/.well-known/openid-configuration` in OAuth.
- The method is a plain `GET` request — no JSON-RPC, no special framing.
  The Agent Card is a static JSON document describing the agent's name,
  capabilities, supported features, and auth requirements.
- `timeout=10.0` is a short timeout because this should be a fast, cacheable
  response. In production, you would cache the Agent Card.

**Key insight**: Agent Card discovery is the **entry point** for all A2A
communication. A client must fetch the card before it knows what methods the
agent supports, what auth it requires, or what input modalities it accepts.
This is analogous to fetching an OpenAPI spec before calling a REST API.

---

### 4. `send_message()` — Synchronous JSON-RPC (lines 85–127, Features F2, F6)

```python
async def send_message(self, text: str, task_id: Optional[str] = None) -> dict:
    rpc_id = str(uuid.uuid4())
    message = {
        "role": "user",
        "parts": [{"kind": "text", "text": text}],
    }
    params: dict = {"message": message}
    if task_id:
        params["taskId"] = task_id

    payload = {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": "message/send",
        "params": params,
    }
```

**Explain to students:**

- This is the core of A2A communication — a JSON-RPC 2.0 request to the
  `message/send` method (Feature F2).
- Walk through the four required JSON-RPC fields:
  1. `"jsonrpc": "2.0"` — protocol version identifier (always this value)
  2. `"id"` — a UUID correlating the request with its response
  3. `"method"` — the A2A operation: `message/send`
  4. `"params"` — the A2A-specific payload containing the message
- The `message` object follows the A2A Message schema: `role` is `"user"`,
  and `parts` is an array of content parts. Here we use `"kind": "text"`,
  but the protocol also supports `"kind": "file"`, `"kind": "data"`, etc.
- The optional `task_id` parameter enables **multi-turn conversation**
  (Feature F6). When provided, the server appends this message to an
  existing task/conversation rather than creating a new one.

**Teaching moment**: Ask students: "Why JSON-RPC instead of plain REST?"
Answer: JSON-RPC gives you a uniform interface — one URL, one HTTP method
(POST), with the operation specified in the `method` field. This simplifies
routing and makes it easy to multiplex many operations over a single
endpoint. It also standardises error handling via the `error` field.

**Second teaching moment**: The response handling at lines 125–127:

```python
if "error" in result:
    raise RuntimeError(f"A2A error: {result['error']}")
return result.get("result", result)
```

This is standard JSON-RPC error handling: check for an `error` key first,
then extract the `result`. The `get("result", result)` fallback handles
edge cases where the response structure varies between implementations.

---

### 5. `stream_message()` — SSE Streaming (lines 129–170, Feature F3)

```python
async def stream_message(self, text: str) -> AsyncIterator[dict]:
    async with client.stream(
        "POST",
        self.base_url + "/",
        json=payload,
        headers={**self._headers, "Accept": "text/event-stream"},
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                data_str = line[len("data:"):].strip()
                if data_str and data_str != "[DONE]":
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        pass
```

**Explain to students:**

- This is Feature F3 — SSE Streaming (`message/stream`). The request payload
  is identical to `message/send` except the `method` is `"message/stream"`
  and the `Accept` header is `"text/event-stream"`.
- **SSE (Server-Sent Events)** is a W3C standard for server-to-client
  streaming over HTTP/1.1. Each event is a line starting with `data:`.
  The stream ends with `data: [DONE]`.
- The parsing logic handles three cases:
  1. Lines starting with `data:` that contain valid JSON — yield the parsed dict
  2. `data: [DONE]` — the sentinel indicating the stream is complete (skip it)
  3. Empty lines or keepalive pings — silently ignored
- `json.JSONDecodeError` is caught because some servers send non-JSON
  keepalive lines or malformed fragments. Silently skipping these is the
  pragmatic approach for a demo client.
- The method is an `AsyncIterator` (uses `yield`), so callers consume it
  with `async for event in client.stream_message(...)`.

**Teaching moment**: Compare this to `send_message()`. The request is the
same shape; only the method name and response handling differ. This is A2A's
design elegance — sync and streaming are parallel operations with identical
input formats.

**Key detail**: `timeout=120.0` is much longer than the 60s for
`send_message()`. Streaming responses can take longer because the server
generates tokens incrementally. Setting the timeout too low would cut off
long responses.

---

### 6. `get_task()` — Task Polling (lines 172–198, Feature F5)

```python
async def get_task(self, task_id: str) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tasks/get",
        "params": {"id": task_id},
    }
```

**Explain to students:**

- Feature F5 — Task Polling via `tasks/get`. After sending a message, the
  client receives a task ID. It can later poll for the task's current status
  and any artifacts produced.
- The payload follows the same JSON-RPC 2.0 pattern — only the `method` and
  `params` change.
- This is the **pull model**: the client periodically asks "is my task done
  yet?" The complementary **push model** is covered by push notifications
  (next section).

**Teaching moment**: When would you use polling vs. streaming vs. push
notifications?
- **Streaming** (F3): When you want real-time incremental output (e.g.,
  token-by-token generation)
- **Polling** (F5): When your client cannot maintain a long-lived connection
  (e.g., serverless functions, mobile apps with intermittent connectivity)
- **Push notifications** (F4): When you want event-driven updates without
  holding a connection open

---

### 7. `set_push_notification_config()` — Webhooks (lines 200–237, Feature F4)

```python
async def set_push_notification_config(
    self, task_id: str, webhook_url: str, token: Optional[str] = None
) -> dict:
    config: dict = {"url": webhook_url}
    if token:
        config["token"] = token

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tasks/pushNotificationConfig/set",
        "params": {
            "taskId": task_id,
            "pushNotificationConfig": config,
        },
    }
```

**Explain to students:**

- Feature F4 — Push Notifications. The client registers a webhook URL for a
  specific task. When the task's status changes, the server POSTs a
  notification to that URL.
- The `token` parameter is optional authentication for the webhook endpoint.
  When provided, the server includes it in webhook requests so the receiver
  can verify the notification's authenticity.
- The method name `tasks/pushNotificationConfig/set` is one of the longer
  JSON-RPC methods in the A2A spec. It follows the resource/action naming
  convention: `tasks` (resource) / `pushNotificationConfig` (sub-resource) /
  `set` (action).

**Teaching moment**: This is the same pattern Stripe, GitHub, and Slack use
for webhooks. The difference is that A2A standardises how to register a
webhook — it is part of the protocol, not a separate admin API.

---

### 8. `run_demo()` — Putting It All Together (lines 242–285, Feature F24)

```python
async def run_demo() -> None:
    client = A2ADemoClient(settings.WEATHER_AGENT_URL)

    # Step 1: Fetch Agent Card
    card = await client.fetch_agent_card()

    # Step 2: Synchronous message/send
    result = await client.send_message("What is the weather in London?")

    # Step 3: SSE streaming
    async for event in client.stream_message("Give me a 5-day forecast for Paris."):
        console.print(f"  SSE Event: {json.dumps(event)}")
```

**Explain to students:**

- The demo follows the natural A2A lifecycle: **discover** (card) ->
  **communicate** (send/stream) -> **observe** (results).
- It targets the `weather_agent`, which is intentionally the simplest agent
  (no auth required, deterministic responses).
- Each step has error handling with a clear fallback message pointing the
  student to the agent URL. This is important for a teaching demo — when
  things fail, the error message should tell you what to do next.
- `settings.WEATHER_AGENT_URL` comes from `shared/config.py`, defaulting to
  `http://localhost:8001`. This means the weather agent must be running before
  you execute this demo.

**Live demo tip**: Run the weather agent in one terminal, then run
`python -m a2a_client.client` in another. Students see the client discover
the agent, send a message, get a response, and stream a second response.
The whole interaction takes about 5 seconds.

---

## Design Patterns to Highlight

1. **Protocol-First Interoperability (F24)**: The entire file proves that A2A
   is a wire protocol, not a library API. Any HTTP client that can POST JSON
   and read SSE can be an A2A client. This is the same principle that makes
   REST APIs language-agnostic.

2. **JSON-RPC 2.0 as a Transport Envelope**: Every A2A operation uses the
   same four-field structure (`jsonrpc`, `id`, `method`, `params`). This
   uniformity means you can write a generic `_rpc_call()` helper and reduce
   all methods to one-liners. The code deliberately does NOT do this, to keep
   each method self-documenting for teaching.

3. **SSE for Streaming**: Server-Sent Events over HTTP/1.1 is simpler than
   WebSockets for unidirectional server-to-client streaming. The A2A protocol
   chose SSE because it works through proxies, load balancers, and CDNs
   without special configuration.

4. **Separation of Auth from Logic**: Auth headers are set once in the
   constructor and automatically included in every request. Individual methods
   never think about authentication.

5. **AsyncIterator for Streaming**: The `stream_message()` method uses
   Python's `async for` protocol, making it composable with any async
   consumer. Callers can process events one at a time without buffering the
   entire response.

---

## Common Student Questions

1. **"Why not use the a2a-sdk's built-in `A2AClient` class?"** Because this
   file exists to prove you don't need it. The a2a-sdk client is convenient
   (it handles JSON-RPC framing, SSE parsing, retries, etc.), but the point
   of F24 is that the protocol is simple enough to implement from scratch.
   In production, use the SDK; for understanding, build it yourself.

2. **"Why does each method create a new `httpx.AsyncClient`?"** This is a
   simplification for the demo. In production, you would create one
   `AsyncClient` instance (with connection pooling) and reuse it across
   calls. Creating a client per request adds TCP connection overhead.

3. **"What happens if the agent is not running?"** `httpx` raises a
   `ConnectError`. The demo's `try/except` blocks catch this and print a
   helpful message: "Make sure weather_agent is running at ...". This is
   intentional — the error path is part of the teaching.

4. **"How would you add retry logic?"** httpx supports a `transport` parameter
   with `httpx.AsyncHTTPTransport(retries=3)`. Alternatively, use the `tenacity`
   library for exponential backoff. The a2a-sdk client handles retries for you
   — another reason to use it in production.

5. **"Can this client talk to non-Python agents?"** Yes. That is the entire
   point. A2A is language-agnostic. This Python client can talk to agents
   written in Go, Java, TypeScript, or any language that implements the A2A
   HTTP API. The protocol is the contract, not the implementation language.

---

## Related Files

- `shared/config.py` — Source of `settings.WEATHER_AGENT_URL`
- `shared/auth.py` — Server-side auth verification (counterpart to the auth
  headers attached in the constructor)
- `a2a_client/grpc_client.py` — Same logical operations but over gRPC/Protobuf
  instead of HTTP/JSON-RPC (compare side-by-side for transport flexibility)
- `weather_agent/agent.py` — The server this client talks to in `run_demo()`
- `orchestrator_agent/agent.py` — Uses `RemoteA2aAgent` (the SDK way) to do
  the same thing this client does manually
- `tests/test_a2a_client.py` — Tests for this client module
