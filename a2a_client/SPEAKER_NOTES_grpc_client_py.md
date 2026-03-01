# Speaker Notes — `a2a_client/grpc_client.py`

> **File**: `a2a_client/grpc_client.py` (321 lines)
> **Purpose**: A2A gRPC client demonstrating Protobuf-over-HTTP/2 as an alternative transport to JSON-RPC-over-HTTP/1.1.
> **Estimated teaching time**: 20–25 minutes

---

## Why This File Matters

The A2A Protocol is **transport-agnostic**. The primary binding is JSON-RPC
over HTTP, but the v0.3 spec introduced a gRPC binding (Feature F21). This
file proves that the same logical operations — discover, send, stream, poll —
work identically over gRPC with Protobuf serialisation.

The teaching message:

> "Look at `client.py` and `grpc_client.py` side by side. Same operations,
> same semantics, different wire format. The protocol is the abstraction,
> not the transport."

This file also demonstrates a practical concern: not every environment has
`grpcio` installed. The graceful import pattern (`HAS_GRPC` flag) shows how
to make gRPC support optional without breaking the rest of the codebase.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–41)

```python
try:
    import grpc
    import grpc.aio
    from a2a.grpc import a2a_pb2, a2a_pb2_grpc
    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False
```

**Explain to students:**

- The `a2a-sdk` ships **pre-compiled Protobuf stubs** in `a2a.grpc.a2a_pb2`
  and `a2a.grpc.a2a_pb2_grpc`. You do not need to run `protoc` or
  `grpc_tools.protoc` yourself. This is a deliberate convenience from the
  SDK maintainers — gRPC setup is notoriously painful, and pre-compiled
  stubs eliminate the most common source of frustration.
- `a2a_pb2` contains the **message classes** (protobuf data types):
  `Part`, `Message`, `SendMessageRequest`, `GetAgentCardRequest`, etc.
- `a2a_pb2_grpc` contains the **service stub**: `A2AServiceStub`, which
  provides the RPC methods (`SendMessage`, `SendStreamingMessage`, etc.).
- The `try/except ImportError` pattern is the standard way to make a heavy
  dependency optional. If `grpcio` is not installed, `HAS_GRPC` is `False`,
  and the class raises a clear `ImportError` at construction time rather
  than failing with a cryptic missing-module error deep inside a method.

**Teaching moment**: This is a real-world pattern. Many libraries ship with
optional gRPC support — e.g., Google Cloud client libraries support both
REST and gRPC transports. The import guard pattern lets you install only
what you need.

---

### 2. `A2AGrpcClient.__init__` (lines 44–72)

```python
class A2AGrpcClient:
    def __init__(
        self,
        host: str = _DEFAULT_GRPC_HOST,
        port: int = _DEFAULT_GRPC_PORT,
        use_tls: bool = False,
    ) -> None:
        if not HAS_GRPC:
            raise ImportError(
                "grpcio and a2a-sdk[grpc] are required. "
                "Run: pip install grpcio a2a-sdk"
            )
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[a2a_pb2_grpc.A2AServiceStub] = None
```

**Explain to students:**

- Compare this constructor to `A2ADemoClient.__init__` in `client.py`. The
  HTTP client takes a `base_url` (a complete URL); the gRPC client takes
  `host` and `port` separately. This reflects the different addressing
  models: HTTP uses URLs, gRPC uses host:port targets.
- `use_tls` defaults to `False` for local development. In production, you
  must use TLS — gRPC over insecure channels is blocked by most cloud
  load balancers.
- The `_channel` and `_stub` are initialized to `None` and populated by
  `connect()`. This is the **explicit lifecycle** pattern — the client
  must be connected before use, and disconnected when done.

**Key contrast with the HTTP client**: The HTTP client creates a new
`httpx.AsyncClient` per method call (stateless). The gRPC client maintains
a persistent channel (stateful). This mirrors the fundamental difference
between HTTP/1.1 (request-response) and HTTP/2 (multiplexed streams over
a long-lived connection).

---

### 3. `connect()` / `disconnect()` — Channel Lifecycle (lines 74–97)

```python
async def connect(self) -> None:
    target = f"{self.host}:{self.port}"
    if self.use_tls:
        credentials = grpc.ssl_channel_credentials()
        self._channel = grpc.aio.secure_channel(target, credentials)
    else:
        self._channel = grpc.aio.insecure_channel(target)

    self._stub = a2a_pb2_grpc.A2AServiceStub(self._channel)

async def disconnect(self) -> None:
    if self._channel:
        await self._channel.close()
        self._channel = None
        self._stub = None
```

**Explain to students:**

- gRPC channels are **long-lived, multiplexed connections**. A single channel
  can handle many concurrent RPCs. This is fundamentally different from HTTP
  clients that open a new TCP connection per request (or use connection
  pooling as an optimization).
- `grpc.aio.secure_channel` vs `grpc.aio.insecure_channel` — the async
  variants from `grpc.aio` integrate with Python's `asyncio` event loop.
  The sync variants (`grpc.secure_channel`) would block the event loop.
- `A2AServiceStub(self._channel)` creates a stub — a local proxy object
  whose methods map 1:1 to the server's RPC methods. Calling
  `self._stub.SendMessage(request)` generates a protobuf-encoded HTTP/2
  request to the server's `SendMessage` handler.
- `disconnect()` explicitly closes the channel and nulls the references.
  This is important for resource cleanup — open gRPC channels hold TCP
  connections and background threads.

**Teaching moment**: The `_ensure_connected()` guard (lines 99–104) is a
defensive pattern. Every RPC method calls it first. Without this, a method
called before `connect()` would fail with an opaque `AttributeError: 'NoneType'
object has no attribute 'SendMessage'`. The guard turns that into a clear
`RuntimeError` with actionable instructions.

---

### 4. `get_agent_card()` — Agent Discovery via gRPC (lines 106–125, Feature F1)

```python
async def get_agent_card(self) -> dict:
    self._ensure_connected()
    request = a2a_pb2.GetAgentCardRequest()
    response = await self._stub.GetAgentCard(request)
    return {
        "name": response.name,
        "description": response.description,
        "url": response.url,
        "version": response.version,
    }
```

**Explain to students:**

- Same logical operation as `fetch_agent_card()` in the HTTP client, but the
  mechanics are different:
  - HTTP: `GET /.well-known/agent.json` -> parse JSON
  - gRPC: `GetAgentCard(GetAgentCardRequest())` -> access proto fields
- The protobuf request is an **empty message** (`GetAgentCardRequest()` with
  no fields). This is the gRPC equivalent of a GET request with no body.
- The response is a protobuf message with typed fields (`response.name`,
  `response.description`). We convert it to a plain dict for consistency
  with the HTTP client's return type.

**Teaching moment**: Notice that the HTTP client returns whatever JSON the
server sends (could be any shape). The gRPC client returns a strongly-typed
protobuf message — the schema is enforced by the `.proto` definition at
compile time. This is one of gRPC's advantages: schema enforcement prevents
the "field name typo" bugs that plague JSON APIs.

---

### 5. `send_message()` — Unary RPC (lines 127–166, Features F21, F6)

```python
async def send_message(self, text: str, task_id: Optional[str] = None) -> dict:
    self._ensure_connected()

    part = a2a_pb2.Part(text=text)
    message = a2a_pb2.Message(
        message_id=str(uuid.uuid4()),
        role=a2a_pb2.ROLE_USER,
        content=[part],
    )
    if task_id:
        message.task_id = task_id

    request = a2a_pb2.SendMessageRequest(message=message)
    response = await self._stub.SendMessage(request)
```

**Explain to students:**

- Compare the message construction side by side with the HTTP client:
  - **HTTP**: `{"role": "user", "parts": [{"kind": "text", "text": text}]}`
  - **gRPC**: `a2a_pb2.Message(role=a2a_pb2.ROLE_USER, content=[a2a_pb2.Part(text=text)])`
- Same semantic content, different encoding. The JSON version uses string
  literals for the role (`"user"`); the protobuf version uses an enum
  constant (`ROLE_USER`). The JSON version nests parts with a `kind`
  discriminator; the protobuf version uses typed fields in the `Part` message.
- `message_id=str(uuid.uuid4())` — the gRPC message requires an explicit
  message ID. In the HTTP client, the JSON-RPC `id` serves a similar purpose
  but at the transport level, not the message level.
- Multi-turn support (F6) works the same way: pass `task_id` to continue an
  existing conversation.

**Teaching moment**: The response extraction (lines 162–166) uses `getattr`
with fallbacks:

```python
task = response.task if hasattr(response, "task") else response
return {
    "task_id": getattr(task, "id", None),
    "status": getattr(task.status, "state", None) if hasattr(task, "status") else None,
}
```

This defensive coding is necessary because protobuf responses have a
`HasField()` semantic — an unset field and a default-valued field are
different things. The `hasattr`/`getattr` pattern handles both cases
gracefully. In production, you would use the proto's `HasField()` method
instead.

---

### 6. `stream_message()` — Server-Side Streaming RPC (lines 168–220, Feature F21)

```python
async def stream_message(self, text: str) -> AsyncIterator[dict]:
    self._ensure_connected()

    request = a2a_pb2.SendMessageRequest(message=message)

    async for stream_response in self._stub.SendStreamingMessage(request):
        if hasattr(stream_response, "task_status_update_event"):
            evt = stream_response.task_status_update_event
            event_dict = {
                "event": "TaskStatusUpdateEvent",
                "task_id": getattr(evt, "task_id", None),
                ...
            }
        elif hasattr(stream_response, "task_artifact_update_event"):
            evt = stream_response.task_artifact_update_event
            event_dict = {
                "event": "TaskArtifactUpdateEvent",
                ...
            }
```

**Explain to students:**

- This is the gRPC equivalent of SSE streaming. The key difference:
  - **SSE** (HTTP): Parse `data:` lines from a text stream, JSON-decode each
  - **gRPC streaming**: Iterate over typed protobuf messages from a
    server-streaming RPC
- `SendStreamingMessage` is a **server-side streaming RPC** — the client sends
  one request and receives a stream of responses. In gRPC terms, this is the
  `rpc SendStreamingMessage(SendMessageRequest) returns (stream StreamResponse)`
  pattern.
- The `stream_response` is a protobuf `oneof` — it contains either a
  `TaskStatusUpdateEvent` or a `TaskArtifactUpdateEvent`. The `hasattr`
  checks determine which variant is present. This is the protobuf equivalent
  of a discriminated union.
- The method yields plain dicts (not protobuf objects) so callers can work
  with standard Python data structures.

**Key contrast with SSE streaming**: In the HTTP client, you parse raw text
lines and handle `[DONE]` sentinels. In the gRPC client, the stream
terminates naturally when the server closes its side — no sentinel needed.
gRPC handles framing, flow control, and connection management at the
transport layer. This is cleaner but requires the gRPC infrastructure.

**Teaching moment**: gRPC server-side streaming uses HTTP/2's built-in
multiplexing. Multiple streams can share a single TCP connection. SSE over
HTTP/1.1 ties up one TCP connection per stream. For high-concurrency
scenarios, gRPC streaming is significantly more efficient.

---

### 7. `get_task()` / `cancel_task()` — Task Management RPCs (lines 222–264, Feature F5)

```python
async def get_task(self, task_id: str) -> dict:
    self._ensure_connected()
    request = a2a_pb2.GetTaskRequest(task_id=task_id)
    task = await self._stub.GetTask(request)
    return {
        "task_id": getattr(task, "id", None),
        "status": getattr(task.status, "state", None) ...
    }

async def cancel_task(self, task_id: str) -> dict:
    self._ensure_connected()
    request = a2a_pb2.CancelTaskRequest(task_id=task_id)
    task = await self._stub.CancelTask(request)
```

**Explain to students:**

- These are straightforward unary RPCs mirroring the JSON-RPC `tasks/get` and
  `tasks/cancel` methods.
- Note that `cancel_task()` does not exist in the HTTP client (`client.py`).
  The gRPC client exposes it because the A2A gRPC service definition includes
  `CancelTask` as a first-class RPC. The HTTP client could implement it
  with a `tasks/cancel` JSON-RPC call, but the demo omits it for simplicity.
- Both methods follow the same pattern: ensure connected, build request,
  call stub, extract response into dict.

**Teaching moment**: The repetition across methods is deliberate. Every RPC
follows the exact same three-step pattern: `_ensure_connected()` -> build
protobuf request -> `await self._stub.MethodName(request)`. In production,
you would factor this into a helper, but for teaching, the repetition makes
each method self-contained and readable.

---

### 8. `run_grpc_demo()` — Demo Runner (lines 270–321, Feature F21)

```python
async def run_grpc_demo() -> None:
    if not HAS_GRPC:
        console.print("[red]grpcio is not installed...[/red]")
        return

    client = A2AGrpcClient(host=_DEFAULT_GRPC_HOST, port=_DEFAULT_GRPC_PORT, use_tls=False)

    try:
        await client.connect()

        # Step 1: Get Agent Card
        card = await client.get_agent_card()

        # Step 2: Send message
        result = await client.send_message("What is the weather in London?")

        # Step 3: Stream message
        async for event in client.stream_message("Give me a forecast for Paris."):
            console.print(f"  gRPC Event: {event}")
    finally:
        await client.disconnect()
```

**Explain to students:**

- The demo mirrors the HTTP client's `run_demo()` exactly: card discovery,
  sync message, streaming. This makes the two demos directly comparable.
- The `HAS_GRPC` check at the top provides a graceful exit if `grpcio` is
  not installed, with actionable instructions for how to install it.
- The `try/finally` block ensures `disconnect()` is always called, even if
  an RPC fails. This is the **resource cleanup** pattern — equivalent to
  `async with` for context managers. The gRPC channel holds system resources
  (TCP connections, background threads) that must be released.
- Each step has its own `try/except` so a failure in one step does not
  prevent the others from running. This is important for demos where the
  gRPC server may support some RPCs but not others.

**Live demo tip**: The gRPC demo requires a gRPC-enabled A2A server, which
is a separate configuration from the standard HTTP servers. If you only have
time for one demo, show the HTTP client first (it works with all agents out
of the box), then show the gRPC client as a "same operations, different
transport" comparison.

---

## Design Patterns to Highlight

1. **Graceful Dependency Degradation**: The `HAS_GRPC` flag pattern lets the
   module exist in the codebase without requiring `grpcio` at import time.
   The class raises at construction, not at import — so importing the module
   for type checking or documentation never fails.

2. **Explicit Connection Lifecycle**: `connect()` / `disconnect()` make the
   channel lifecycle visible. This contrasts with the HTTP client where
   connections are created and destroyed implicitly per request. Both
   approaches are valid; the explicit lifecycle gives more control over
   resource management.

3. **Pre-Compiled Protobuf Stubs**: The `a2a-sdk` ships the stubs so you
   never run `protoc`. This is the "batteries included" approach — removing
   the most common barrier to gRPC adoption (build system integration).

4. **Transport Symmetry**: Every method in this class has a direct counterpart
   in `client.py`. This is not accidental — it reflects the A2A protocol's
   design principle that transport is an implementation detail, not a
   semantic difference.

5. **Defensive Protobuf Access**: Using `hasattr`/`getattr` with fallbacks
   handles the nuances of protobuf field presence. Protobuf fields have
   default values (empty string, zero, etc.) that are indistinguishable
   from "not set" without `HasField()`. The defensive pattern avoids
   `AttributeError` surprises.

---

## Common Student Questions

1. **"When should I use gRPC instead of HTTP/JSON?"** Use gRPC when you need:
   binary efficiency (protobuf is 3-10x smaller than JSON), strict schema
   enforcement (proto definitions catch errors at compile time), bidirectional
   streaming (HTTP/2 multiplexing), or when you are already in a gRPC
   ecosystem (e.g., Kubernetes microservices using gRPC for inter-service
   communication). Use HTTP/JSON when you need: browser compatibility (gRPC
   requires gRPC-Web proxy for browsers), human-readable payloads for
   debugging, simpler tooling (`curl` works with HTTP; gRPC needs `grpcurl`),
   or when your infrastructure does not support HTTP/2.

2. **"Why does the gRPC client need `connect()`/`disconnect()` but the HTTP
   client does not?"** gRPC channels are long-lived multiplexed connections
   optimized for many RPCs over one TCP connection. HTTP clients (especially
   httpx's `AsyncClient`) can also pool connections, but the demo creates a
   new client per call for simplicity. The explicit lifecycle makes gRPC's
   resource model visible.

3. **"What are the pre-compiled protobuf stubs?"** The `.proto` file defines
   the service and message types in Protocol Buffers IDL. Running `protoc`
   (the protobuf compiler) generates Python classes (`_pb2.py` for messages,
   `_pb2_grpc.py` for service stubs). The `a2a-sdk` runs this compilation
   at package build time and ships the generated files, so you never need
   `protoc` installed.

4. **"Can I use gRPC and HTTP simultaneously?"** Yes. In production, many
   services expose both a gRPC endpoint and an HTTP/JSON endpoint (sometimes
   via gRPC-Gateway or Envoy proxy transcoding). The A2A protocol explicitly
   supports both transports, and a server can serve both on different ports.

5. **"Why does `stream_message()` use `hasattr` instead of protobuf's
   `HasField()`?"** `HasField()` only works on `oneof` fields and singular
   message fields — not on scalar fields. The `hasattr` pattern is more
   general and works regardless of the field type. In production code, you
   would use `WhichOneof()` to determine which variant of a `oneof` is set.

---

## Related Files

- `a2a_client/client.py` — The HTTP/JSON-RPC counterpart. Compare method by
  method to see transport symmetry
- `shared/config.py` — Configuration source (though the gRPC client currently
  uses hardcoded defaults for host/port)
- `weather_agent/agent.py` — The agent these clients communicate with (HTTP
  transport; would need a gRPC server wrapper for the gRPC client)
- `orchestrator_agent/agent.py` — Uses `RemoteA2aAgent` from the a2a-sdk,
  which abstracts over the transport layer
- `tests/test_a2a_client.py` — Tests for the client module (may include gRPC
  client tests if `grpcio` is available)
