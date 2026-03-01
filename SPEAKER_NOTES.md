# A2A Protocol Demo — Speaker Notes

> **Purpose**: Comprehensive teaching notes for walking students through
> every aspect of this project. Estimated teaching time: 3–4 hours (full),
> or 90 minutes (highlights only).

---

## Table of Contents

1. [Opening: Why This Project Exists](#1-opening-why-this-project-exists)
2. [What is the A2A Protocol?](#2-what-is-the-a2a-protocol)
3. [What is Google ADK?](#3-what-is-google-adk)
4. [Architecture Overview](#4-architecture-overview)
5. [Project Structure Walkthrough](#5-project-structure-walkthrough)
6. [Shared Infrastructure](#6-shared-infrastructure)
7. [Agent Deep Dives](#7-agent-deep-dives)
   - 7.1 weather_agent
   - 7.2 research_agent
   - 7.3 code_agent
   - 7.4 data_agent
   - 7.5 async_agent
   - 7.6 orchestrator_agent
   - 7.7 pipeline_agent
   - 7.8 parallel_agent
   - 7.9 loop_agent
8. [Standalone Clients](#8-standalone-clients)
9. [Webhook Server](#9-webhook-server)
10. [Authentication Schemes](#10-authentication-schemes)
11. [Callbacks, Guardrails, and Safety](#11-callbacks-guardrails-and-safety)
12. [Testing Strategy](#12-testing-strategy)
13. [Evaluation Framework](#13-evaluation-framework)
14. [Deployment](#14-deployment)
15. [The 24 Features Matrix](#15-the-24-features-matrix)
16. [Live Demo Script](#16-live-demo-script)
17. [Key Design Decisions and Trade-offs](#17-key-design-decisions-and-trade-offs)
18. [Common Student Questions](#18-common-student-questions)

---

## 1. Opening: Why This Project Exists

**Key message to students:**

> "Imagine you're building an enterprise AI system. You don't want one
> monolithic agent that does everything. You want *specialist agents* that
> each do one thing well — a weather expert, a research analyst, a code
> executor — and an *orchestrator* that routes questions to the right
> specialist. But how do these agents discover each other? How do they
> communicate? How do they handle authentication, streaming, long-running
> tasks, and errors? That's what the A2A Protocol solves."

This project is a **complete, runnable reference implementation** of the
Agent-to-Agent (A2A) Protocol specification v0.3. It demonstrates all 24
features of the protocol using Google's Agent Development Kit (ADK) 1.25.1.

**What makes this demo valuable:**
- It's not a toy. Every agent is a real microservice with real auth, real
  streaming, real async task management.
- It covers the *entire* A2A spec — from basic discovery to gRPC transport.
- It's production-structured: config management, test suite, CI/CD scripts,
  Docker deployment.
- 300 passing tests prove it works.

---

## 2. What is the A2A Protocol?

### The Problem It Solves

Today, AI agents are siloed. A LangChain agent can't talk to a CrewAI
agent. An AutoGen agent can't discover a Vertex AI agent's capabilities.
Every framework has its own proprietary communication format.

**A2A is the HTTP of the agent world** — an open protocol that lets any
agent talk to any other agent, regardless of the framework they were built
with.

### Core Concepts

**Explain these to students:**

1. **Agent Card** (`/.well-known/agent.json`):
   - Every A2A agent publishes a JSON document at a well-known URL
   - Contains: name, description, skills (what it can do), capabilities
     (streaming, push notifications), authentication requirements
   - Think of it as a "business card" for an AI agent
   - Any client can discover what an agent does by reading this card

2. **JSON-RPC 2.0**:
   - All A2A communication uses JSON-RPC 2.0 over HTTP
   - Standard format: `{"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {...}}`
   - Methods: `message/send`, `message/stream`, `tasks/get`, `tasks/cancel`,
     `tasks/list`, `tasks/pushNotificationConfig/set`, `tasks/pushNotificationConfig/get`

3. **Task Lifecycle**:
   - Every interaction creates a **Task** with an ID
   - States: `submitted` → `working` → `completed` / `failed` / `canceled`
   - Special state: `input-required` (agent needs more info from the user)
   - Tasks have history (conversation turns) and artifacts (generated files)

4. **Message Structure**:
   - Messages have a `role` ("user" or "agent") and `parts` array
   - Part types: `TextPart`, `FilePart` (binary data or URI), `DataPart` (structured JSON)

### Protocol vs SDK vs Framework

Draw this distinction clearly:

| Layer | What It Is | Example |
|-------|-----------|---------|
| **A2A Protocol** | The specification (like HTTP spec) | JSON-RPC methods, Agent Card schema |
| **a2a-sdk** | Reference implementation of the protocol | Python package, pre-compiled gRPC stubs |
| **Google ADK** | Agent framework that implements A2A | LlmAgent, RemoteA2aAgent, to_a2a() |

**Key point**: You can build an A2A-compliant agent *without* ADK. The
`a2a_client/client.py` in this project proves it — it uses only `httpx`.

---

## 3. What is Google ADK?

**Google Agent Development Kit (ADK)** is an open-source framework for
building AI agents. Version 1.25.1 is used in this project.

### Key ADK Concepts

1. **LlmAgent**: An agent backed by an LLM (Gemini). Has:
   - `model`: Which Gemini model to use (e.g., `gemini-2.0-flash`)
   - `instruction`: System prompt that defines the agent's personality
   - `tools`: Python functions the LLM can call (auto-schema from type hints)
   - `sub_agents`: Other agents this one can delegate to
   - `code_executor`: For sandboxed code execution
   - `output_key`: Where to store output in session state
   - Callbacks: `before_model_callback`, `after_model_callback`,
     `before_tool_callback`, `after_tool_callback`

2. **Workflow Agents** (no LLM, deterministic orchestration):
   - `SequentialAgent`: Runs sub-agents in order (A → B → C)
   - `ParallelAgent`: Runs sub-agents concurrently (fan-out)
   - `LoopAgent`: Repeats sub-agents until exit condition or max iterations

3. **RemoteA2aAgent**: A proxy that delegates to a remote A2A server.
   Discovers capabilities by fetching the agent card at construction time.

4. **to_a2a()**: Converts any ADK agent into an A2A-compliant FastAPI/Starlette
   web application with the standard JSON-RPC endpoint and agent card route.

5. **Runner**: Manages agent execution with session and memory services.

6. **Session State**: `context.state` — a dict shared across all agents in
   a session. Each agent can read/write keys.

7. **Memory Service**: Long-term storage that persists across sessions
   (InMemoryMemoryService for dev, VertexAiRagMemoryService for prod).

### ADK CLI Commands

```bash
adk run ./agent_dir/     # Terminal chat with an agent
adk web ./agent_dir/     # Browser-based Dev UI
adk api_server --a2a --port 8001 ./agent_dir/  # A2A HTTP server
adk eval ./evals/file.json  # Run evaluation suite
```

---

## 4. Architecture Overview

### Draw this diagram on the whiteboard:

```
                     ┌──────────────────────┐
                     │       User           │
                     │  (Browser / CLI)     │
                     └─────────┬────────────┘
                               │ natural language
                               ▼
                     ┌──────────────────────┐
                     │  orchestrator_agent   │  ← Root LLM Agent
                     │  (Vertex AI Engine)   │  ← 5 RemoteA2aAgent sub-agents
                     │  Port: ADK Dev UI     │  ← 2 local function tools
                     └─────────┬────────────┘
                               │ A2A Protocol (JSON-RPC 2.0)
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼──────┐
    │ weather_agent  │ │ research     │ │ code_agent  │
    │ :8001          │ │ _agent :8002 │ │ :8003       │
    │ No Auth        │ │ Bearer JWT   │ │ API Key     │
    │ Function Tools │ │ google_search│ │ code_exec   │
    └────────────────┘ └──────────────┘ └─────────────┘

    ┌─────────────────┐ ┌───────────────────────────────┐
    │ data_agent      │ │ async_agent                   │
    │ :8004           │ │ :8005                         │
    │ OAuth 2.0       │ │ Custom FastAPI (no ADK)       │
    │ CSV Artifacts   │ │ Push Notifications + SSE      │
    └─────────────────┘ │ Background tasks + Cancel     │
                        └──────────────┬────────────────┘
                                       │ HTTP POST (webhook)
                                       ▼
                        ┌───────────────────────────────┐
                        │ webhook_server :9000           │
                        │ Receives push notifications   │
                        │ HMAC signature verification   │
                        └───────────────────────────────┘
```

### Workflow Agents (local, not networked):

```
pipeline_agent:  fetch_agent → analyze_agent → report_agent  (Sequential)
parallel_agent:  [London, Tokyo, NYC, Sydney, Paris] → aggregator  (Parallel → Sequential)
loop_agent:      start_task → [poll + check_exit] × 10  (Sequential → Loop)
```

### Communication patterns:

| Pattern | Example | A2A Method |
|---------|---------|------------|
| Sync request/response | "Weather in Paris?" | `message/send` |
| Streaming | "5-day forecast for Tokyo" | `message/stream` (SSE) |
| Async with push | "Run 20-second simulation" | `message/send` + webhook |
| Polling | Loop agent checks task status | `tasks/get` |
| Cancellation | Stop a running task | `tasks/cancel` |
| Multi-turn | "Research AI" → "Focus on safety" | `message/send` with `taskId` |

---

## 5. Project Structure Walkthrough

**Walk students through each directory, explaining the purpose:**

```
A2A_Research_demo_1/
│
├── .env                    ← Runtime configuration (GCP project, API keys, agent URLs)
├── .env.example            ← Template — never commit real .env
├── .gitignore              ← Ignores .env, __pycache__, *.json (except evals + package.json)
├── requirements.txt        ← Pinned dependencies
├── README.md               ← Project overview
├── ENV_SETUP.md            ← GCP setup guide
├── DEMO.md                 ← Step-by-step feature walkthroughs
├── PLAN.md                 ← Implementation checklist
│
├── shared/                 ← Shared code used by ALL agents
│   ├── __init__.py
│   ├── config.py           ← Settings dataclass + .env loader + validation
│   ├── auth.py             ← API Key, Bearer JWT, HMAC verification
│   └── callbacks.py        ← Logging, guardrails, caching callbacks
│
├── weather_agent/          ← Simplest A2A agent (good starting point)
│   ├── __init__.py
│   ├── agent.py            ← Agent Card + LlmAgent + to_a2a() app
│   └── tools.py            ← get_weather(), get_forecast() async functions
│
├── research_agent/         ← Most complex auth + extended card
│   ├── __init__.py
│   └── agent.py            ← Bearer JWT + extended card + memory service
│
├── code_agent/             ← Sandboxed code execution
│   ├── __init__.py
│   └── agent.py            ← BuiltInCodeExecutor + safety guardrails
│
├── data_agent/             ← Structured data + artifacts
│   ├── __init__.py
│   ├── agent.py            ← OAuth 2.0 middleware
│   └── tools.py            ← CSV parsing, statistics, report generation
│
├── async_agent/            ← Custom A2A implementation (no ADK LlmAgent)
│   ├── __init__.py
│   └── agent.py            ← Full JSON-RPC handler, task lifecycle, webhooks
│
├── orchestrator_agent/     ← Root agent that routes to specialists
│   ├── __init__.py
│   ├── agent.py            ← 5 RemoteA2aAgent sub-agents + routing prompt
│   ├── tools.py            ← list_available_agents(), get_agent_status()
│   └── callbacks.py        ← Safety prefix injection + URL redaction
│
├── pipeline_agent/         ← 3-stage sequential pipeline
│   ├── __init__.py
│   └── agent.py            ← fetch → analyze → report via session state
│
├── parallel_agent/         ← Fan-out weather queries
│   ├── __init__.py
│   └── agent.py            ← 5 city agents in parallel → aggregator
│
├── loop_agent/             ← Polling loop for async tasks
│   ├── __init__.py
│   └── agent.py            ← RemoteA2aAgent + LoopAgent with exit condition
│
├── a2a_client/             ← Standalone clients (no ADK)
│   ├── __init__.py
│   ├── client.py           ← HTTP/JSON-RPC client (httpx only)
│   └── grpc_client.py      ← gRPC client (a2a-sdk stubs)
│
├── webhook_server/         ← Push notification receiver
│   ├── __init__.py
│   └── main.py             ← FastAPI app, HMAC verification, event logging
│
├── evals/                  ← ADK evaluation datasets
│   ├── eval_config.yaml    ← Scoring criteria + thresholds
│   ├── orchestrator_eval.json
│   ├── weather_eval.json
│   ├── research_eval.json
│   ├── code_eval.json
│   └── data_eval.json
│
├── protos/                 ← gRPC protobuf definitions
│   └── a2a_demo.proto      ← Demo A2A gRPC service definition
│
├── scripts/                ← Shell scripts for dev and deployment
│   ├── start_all.sh        ← Start all agent servers locally
│   ├── stop_all.sh         ← Stop all background processes
│   └── deploy_cloud_run.sh ← Deploy to Google Cloud Run
│
└── tests/                  ← 300 pytest tests
    ├── pytest.ini           ← Test configuration (asyncio_mode=auto)
    ├── conftest.py          ← Shared fixtures (mock env, payloads)
    ├── test_config.py
    ├── test_weather_agent.py
    ├── test_async_agent.py
    ├── test_async_agent_lifecycle.py
    ├── test_webhook_server.py
    ├── test_shared_auth.py
    ├── test_shared_callbacks.py
    ├── test_a2a_client.py
    ├── test_orchestrator_tools.py
    ├── test_orchestrator_callbacks.py
    ├── test_data_agent.py
    └── ..._extended.py      ← Extended test suites
```

**Teaching tip**: Start with `weather_agent/` — it's the simplest. Then
layer complexity: auth (code_agent), streaming (research_agent), async
(async_agent), orchestration (orchestrator_agent).

---

## 6. Shared Infrastructure

### 6.1 Configuration (`shared/config.py`)

**Key points to explain:**

```python
@dataclass
class Settings:
    GOOGLE_CLOUD_PROJECT: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    )
    # ... 14 more fields
```

- Uses Python `dataclass` — typed, inspectable, testable
- `default_factory=lambda: os.environ.get(...)` reads from environment at
  instantiation time, not import time
- `dotenv` loads `.env` file before the dataclass is created
- `validate()` method checks all required fields are set
- **Guard for tests**: `if "pytest" not in sys.modules: settings.validate()`
  prevents test collection from failing when `.env` is missing
- **Singleton pattern**: `settings = Settings()` — one instance, imported everywhere

**Why this matters**: Every agent imports `from shared.config import settings`.
One source of truth for all configuration. Change a URL in `.env`, all agents
pick it up.

### 6.2 Authentication (`shared/auth.py`)

This file implements four auth schemes. Walk through each:

**API Key (`verify_api_key`)**:
```python
def verify_api_key(api_key = Security(_api_key_header)) -> str:
    if not api_key or api_key != settings.CODE_AGENT_API_KEY:
        raise HTTPException(status_code=403)
    return api_key
```
- Extracts `X-API-Key` header via FastAPI's `Security` dependency injection
- Simple string comparison (demo grade — use constant-time compare in prod)

**Bearer JWT (`create_bearer_token` + `verify_bearer_token`)**:
```python
def create_bearer_token(subject: str, ttl_seconds: int = 3600) -> str:
    header = base64url({"alg": "HS256", "typ": "JWT"})
    payload = base64url({"sub": subject, "iat": now, "exp": now + ttl})
    signature = HMAC-SHA256(key, f"{header}.{payload}")
    return f"{header}.{payload}.{signature}"
```
- Hand-rolled JWT with HMAC-SHA256 (for teaching — use `python-jose` in prod)
- Three-part token: `header.payload.signature`
- Verification: recompute signature, compare, check expiry

**Webhook HMAC (`verify_webhook_signature`)**:
```python
def verify_webhook_signature(body: bytes, sig_header: str) -> bool:
    expected = HMAC-SHA256(WEBHOOK_AUTH_TOKEN, body).hexdigest()
    actual = sig_header[len("sha256="):]
    return hmac.compare_digest(expected, actual)
```
- Uses `hmac.compare_digest` (constant-time comparison) to prevent timing attacks
- Sender computes `sha256=<hex>`, receiver verifies

### 6.3 Callbacks (`shared/callbacks.py`)

**Explain the callback model:**

ADK agents have 6 callback hooks. Each returns `None` (pass through) or a
value (intercept/modify):

```
User message → [before_agent] → [before_model] → LLM → [after_model] → [before_tool] → Tool → [after_tool] → Response → [after_agent]
```

This file implements 7 callback functions in 3 categories:

**1. Logging** (observability):
- `logging_callback_before_model`: Logs agent name + message count before
  each LLM call. Uses Rich library for coloured console output.
- `logging_callback_after_model`: Logs token usage (prompt/candidates/total)
  from LLM response metadata.
- `logging_callback_before_tool`: Logs tool name + arguments.
- `logging_callback_after_tool`: Logs tool response keys.

**2. Guardrails** (safety, F17):
```python
_DANGEROUS_PATTERNS = ["os.system", "subprocess", "shutil.rmtree",
                       "__import__", "exec(", "eval(", "open("]

def guardrail_callback_before_tool(tool, tool_args, tool_context):
    code_arg = tool_args.get("code", "")
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in code_arg:
            return {"error": f"Blocked: '{pattern}' is not allowed."}
    return None  # allow
```
- Checks the `code` argument of any tool call for dangerous patterns
- Returns an error dict to block execution (instead of `None` to allow)
- Used by code_agent to prevent sandbox escape

**3. Caching**:
- `cache_callback_before_tool`: Checks `_tool_cache` dict for matching
  (tool_name, args) key. Returns cached result if found.
- `cache_callback_after_tool`: Stores result in cache after execution.
- Simple in-memory dict — not thread-safe, not production-ready.

---

## 7. Agent Deep Dives

### 7.1 weather_agent — The Simplest A2A Agent

**File: `weather_agent/agent.py` (88 lines)**

**Teach this first** — it shows the minimal A2A agent pattern:

```python
# Step 1: Define the Agent Card
_AGENT_CARD = AgentCard(
    name="weather_agent",
    description="Provides weather data for any city worldwide.",
    url=settings.WEATHER_AGENT_URL,
    version="1.0.0",
    skills=[_weather_skill, _forecast_skill],  # What I can do
    capabilities=AgentCapabilities(streaming=True),  # How I can do it
)

# Step 2: Create the LLM Agent
root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,      # "gemini-2.0-flash"
    name="weather_agent",
    instruction="You are a weather assistant...",
    tools=[get_weather, get_forecast],  # Python functions as tools
)

# Step 3: Convert to A2A web application
app = to_a2a(root_agent, port=8001, agent_card=_AGENT_CARD)
```

**That's it.** Three steps: Card → Agent → App. The `to_a2a()` function
automatically creates:
- `GET /.well-known/agent.json` → returns the agent card
- `POST /` → JSON-RPC 2.0 dispatcher (message/send, message/stream, etc.)

**File: `weather_agent/tools.py` — Function Tools (F12)**

```python
async def get_weather(city: str) -> dict:
    """Return current weather conditions for a city."""
    if not settings.OPENWEATHERMAP_API_KEY:
        return _mock_weather(city)  # Fallback for demo

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{_OWM_BASE}/weather", params={...})
        # Parse and return structured dict
```

**Key teaching points:**
- ADK auto-generates the JSON schema from type hints + docstring
- The LLM sees: `get_weather(city: str) -> dict` with the docstring as description
- Mock data fallback means the demo works without an API key
- Functions are `async def` — ADK handles async/sync function tools

**The `_aggregate_forecast()` helper** is a good example of non-trivial data
processing: groups 3-hour OpenWeatherMap slots by date, computes daily
high/low temps, and finds the dominant weather condition.

---

### 7.2 research_agent — Bearer JWT + Extended Card + Memory

**File: `research_agent/agent.py` (228 lines)**

This is the most feature-rich agent. Walk through each layer:

**Layer 1: Two Agent Cards (F7 — Extended Card)**

```python
# Public card — anyone can see basic skills
_PUBLIC_AGENT_CARD = AgentCard(
    skills=[_research_skill],  # web_research only
    ...)

# Authenticated card — premium skill visible after auth
_EXTENDED_AGENT_CARD = AgentCard(
    skills=[_research_skill, _extended_skill],  # + competitive_analysis
    ...)
```

**Why?** In production, you might want free-tier users to see basic
capabilities and paid users to see premium ones. The extended card
endpoint requires a Bearer token.

**Layer 2: Multi-turn Conversation (F6)**

```python
instruction = """
...
3. If the query is ambiguous (e.g., "research AI" without a focus area),
   respond with status input-required and ask the user to clarify.
"""
```

When the LLM detects ambiguity, it returns `input-required` state. The
client sends a follow-up message with the same `taskId` to continue.

**Layer 3: Memory Service (F14)**

```python
_memory_service = InMemoryMemoryService()
_runner = Runner(
    agent=root_agent,
    session_service=InMemorySessionService(),
    memory_service=_memory_service,
)
app = to_a2a(root_agent, runner=_runner, ...)
```

The memory service stores key facts extracted from conversations. In
future sessions, the agent can recall previously learned information.

**Layer 4: Bearer Auth Middleware (F8)**

```python
_OPEN_PATHS = {"/.well-known/agent.json", "/agents/authenticatedExtendedCard"}

async def _bearer_auth_middleware(request, call_next):
    if request.url.path in _OPEN_PATHS:
        return await call_next(request)  # Public endpoints
    # All other endpoints require Bearer token
    token = extract_from_header(request)
    verify_bearer_token(token)
    return await call_next(request)
```

**Key design**: Discovery endpoint is ALWAYS public (so orchestrators can
find agents), but operational endpoints require auth.

**Layer 5: Starlette Composition**

```python
app = Starlette(routes=[
    Route("/agents/authenticatedExtendedCard", _authenticated_extended_card),
    Mount("/", app=_a2a_app),  # Everything else → A2A handler
])
app.add_middleware(BaseHTTPMiddleware, dispatch=_bearer_auth_middleware)
```

The outer Starlette app adds the custom route, then mounts the inner
A2A app. Middleware wraps everything.

---

### 7.3 code_agent — Sandboxed Execution + Safety Guardrails

**File: `code_agent/agent.py` (118 lines)**

**The key concept: Gemini's BuiltInCodeExecutor**

```python
root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    code_executor=BuiltInCodeExecutor(),  # Gemini-managed sandbox
    before_tool_callback=guardrail_callback_before_tool,  # Safety check
)
```

- `BuiltInCodeExecutor()`: Gemini can generate AND execute Python code
  in a sandboxed environment. The sandbox is managed by Google — no local
  code execution happens.
- `guardrail_callback_before_tool`: Inspects the `code` argument before
  execution. Blocks `os.system`, `subprocess`, `eval`, `exec`, `open(`.

**Auth: API Key middleware**

```python
async def _api_key_middleware(request, call_next):
    if request.url.path == "/.well-known/agent.json":
        return await call_next(request)  # Discovery always public
    api_key = request.headers.get("X-API-Key", "")
    if api_key != settings.CODE_AGENT_API_KEY:
        return JSONResponse({"error": "Invalid API key"}, status_code=403)
    return await call_next(request)
```

Simplest auth scheme — just a shared secret in a header.

---

### 7.4 data_agent — Artifacts + OAuth 2.0

**File: `data_agent/agent.py` (157 lines)**

**Artifact pattern (F15)**

The data_agent demonstrates A2A Artifacts — files generated by the agent
and attached to the response:

```python
# In data_agent/tools.py:
def generate_csv_report(title, columns, rows_json) -> dict:
    # Generate CSV content
    return {
        "filename": f"{safe_title}.csv",
        "mime_type": "text/csv",
        "content": csv_content,  # The actual CSV string
        "row_count": len(rows),
    }
```

The returned dict contains the file content. ADK's framework can expose
this as a `FilePart` artifact in the A2A response.

**Other data tools:**
- `parse_csv_data()`: Parses raw CSV text into structured rows/columns.
  Auto-detects delimiter (comma, tab, semicolon).
- `compute_statistics()`: Computes mean, median, stdev, min, max, sum on
  a JSON list of numbers.

**OAuth 2.0 middleware:**

```python
async def _oauth_middleware(request, call_next):
    token = extract_bearer_token(request)

    # Demo mode: accept the demo token directly
    if token == settings.CODE_AGENT_API_KEY:
        return await call_next(request)

    # Production mode: verify via google-auth
    id_token.verify_oauth2_token(token, transport_request)
```

Two verification paths: demo token for local dev, real Google OAuth for
production. This is a common pattern in GCP applications.

---

### 7.5 async_agent — The Most Complex Agent

**File: `async_agent/agent.py` (548 lines)**

**This is NOT an ADK LlmAgent.** It's a custom FastAPI application that
implements the A2A JSON-RPC 2.0 protocol directly. This is intentional —
it demonstrates that you don't need ADK to build an A2A agent.

**Why it exists:** Long-running tasks (10–60 seconds) need:
- Background execution (don't block the HTTP response)
- Progress tracking (25%, 50%, 75%, 100%)
- Push notifications (webhook delivery)
- SSE streaming (real-time event stream)
- Cancellation (stop a running task)

**Architecture walkthrough:**

```python
# In-memory stores (replace with Redis/DB in production)
_task_store: dict[str, dict] = {}       # task_id → task state
_webhook_store: dict[str, dict] = {}    # task_id → webhook config
_running_tasks: dict[str, asyncio.Task] = {}  # task_id → asyncio.Task
_sse_queues: dict[str, list[Queue]] = {}  # task_id → SSE client queues
```

**Request flow for `message/send`:**

```
1. Client sends POST / with method: "message/send"
2. Handler creates task with status "submitted"
3. Stores task in _task_store
4. Creates asyncio.Task for background execution
5. Stores asyncio.Task in _running_tasks (for cancellation)
6. Returns immediately with the submitted task
7. Background: _execute_long_task() runs for 20 seconds
   - Updates status to "working" at 0%, 25%, 50%, 75%
   - Sends push notifications to registered webhook
   - Broadcasts SSE events to connected clients
   - Finally sets status to "completed" with artifact
```

**Cancellation (the bug we fixed):**

```python
# BEFORE (broken): background_tasks.add_task() never stored the Task
background_tasks.add_task(_execute_long_task, task_id)
# _running_tasks was always empty → cancel found nothing

# AFTER (fixed): asyncio.create_task() returns the Task object
_running_tasks[task_id] = asyncio.create_task(_execute_long_task(task_id))
# Now cancel() can actually cancel the running coroutine
```

**SSE Streaming (F3):**

```python
async def _handle_message_stream(rpc_id, params):
    queue = asyncio.Queue()
    _sse_queues.setdefault(task_id, []).append(queue)
    # Start background task
    _running_tasks[task_id] = asyncio.create_task(_execute_long_task(task_id))

    async def _event_generator():
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=60)
            yield f"data: {json.dumps(event)}\n\n"
            if event is terminal:
                break

    return StreamingResponse(_event_generator(), media_type="text/event-stream")
```

Each SSE client gets its own `asyncio.Queue`. The background task broadcasts
events to all queues. The generator yields SSE-formatted lines until a
terminal state (completed/failed/canceled).

**Push Notifications (F4):**

```python
async def _push_notification(task_id, state, progress):
    config = _webhook_store.get(task_id)
    if not config:
        return  # No webhook registered

    payload = {"event": "TaskStatusUpdateEvent", "taskId": task_id, ...}
    headers = {
        "X-Webhook-Signature": _compute_webhook_signature(body),
        "Authorization": f"Bearer {config.get('token', '')}",
    }

    # Retry with exponential backoff (3 attempts, 1s → 2s → 4s)
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(config["url"], content=body, headers=headers)
                return  # Success
        except httpx.RequestError:
            await asyncio.sleep(delay)
            delay *= 2
```

**Cursor-based pagination (F5):**

```python
def _handle_tasks_list(params):
    cursor = params.get("cursor")
    page_size = clamp(params.get("page_size", 20), 1, 100)
    all_ids = list(_task_store.keys())
    start_idx = all_ids.index(cursor) + 1 if cursor else 0
    page = all_ids[start_idx : start_idx + page_size]
    return {"tasks": [...], "next_cursor": last_id_or_none, "total_count": len(all_ids)}
```

---

### 7.6 orchestrator_agent — The Router

**File: `orchestrator_agent/agent.py` (129 lines)**

The orchestrator is the "brain" of the system. It receives user queries and
routes them to the appropriate specialist agent.

**5 RemoteA2aAgent sub-agents:**

```python
weather_agent = RemoteA2aAgent(
    name="weather_agent",
    description="Handles weather queries for any city.",
    agent_card=f"{settings.WEATHER_AGENT_URL}/.well-known/agent.json",
)
# ... research_agent, code_agent, data_agent, async_agent
```

`RemoteA2aAgent` fetches the agent card at construction time to discover
capabilities. At runtime, when the orchestrator LLM decides to delegate,
`RemoteA2aAgent` sends an A2A `message/send` request to the remote agent.

**System instruction (routing logic):**

```
Your role is to route incoming user requests to the most appropriate
specialist agent from your team:
- weather_agent: Use for weather queries
- research_agent: Use for open-ended research
- code_agent: Use for code generation/execution
- data_agent: Use for data processing
- async_agent: Use for long-running tasks

If a task spans multiple domains, break it into sub-tasks and delegate each.
```

The LLM reads this instruction and decides which sub-agent to call. ADK
handles the actual delegation via `RemoteA2aAgent`.

**Local function tools:**

```python
tools=[list_available_agents, get_agent_status]
```

- `list_available_agents()`: Returns a dict of all configured agents with
  their URLs and descriptions. Helps the LLM know what's available.
- `get_agent_status(agent_name)`: Probes the agent's `/.well-known/agent.json`
  endpoint to check if it's running. Useful for health checks.

**File: `orchestrator_agent/callbacks.py` — Safety + Redaction**

Two orchestrator-specific callbacks:

1. **Safety prefix injection** (before_model):
```python
_SAFETY_PREFIX = (
    "[SAFETY] This orchestrator must never disclose internal agent URLs, "
    "credentials, or API keys. ..."
)
# Injected into system instruction on every model call
```

2. **URL redaction** (after_model):
```python
_REDACTED_PATTERNS = ["localhost", "127.0.0.1", "internal-"]

# Scans model response text, replaces matches with [REDACTED]
text = re.sub(r"https?://\S*localhost\S*", "[REDACTED]", text)
```

**Why?** The LLM might inadvertently include internal URLs in its response
to the user. The after_model callback catches and redacts them.

---

### 7.7 pipeline_agent — Sequential Pipeline with Session State

**File: `pipeline_agent/agent.py` (117 lines)**

**Three-stage assembly line:**

```
fetch_agent → analyze_agent → report_agent
    ↓               ↓               ↓
  raw_data       analysis      final_report
  (state key)   (state key)    (state key)
```

Each stage is an LlmAgent with an `output_key`:

```python
fetch_agent = LlmAgent(
    instruction="Fetch background info on the topic...",
    output_key="raw_data",  # Stores output in context.state["raw_data"]
)

analyze_agent = LlmAgent(
    instruction="Read raw_data from context, extract 3-5 key insights...",
    output_key="analysis",
)

report_agent = LlmAgent(
    instruction="Read analysis from context, generate structured report...",
    output_key="final_report",
)

root_agent = SequentialAgent(
    sub_agents=[fetch_agent, analyze_agent, report_agent],
)
```

**Key concept: `output_key`**

When an LlmAgent has `output_key="raw_data"`, ADK stores the agent's
final response text in `context.state["raw_data"]`. The next agent in
the sequence can read this key from its context.

**Teaching analogy**: It's like an assembly line. Raw materials enter,
each station adds value, the final product exits.

---

### 7.8 parallel_agent — Fan-out / Fan-in

**File: `parallel_agent/agent.py` (96 lines)**

**Pattern: Concurrent queries aggregated into a summary.**

```python
_CITIES = ["London", "Tokyo", "New York", "Sydney", "Paris"]

# Each city gets its own LlmAgent with its own RemoteA2aAgent
def _make_city_agent(city):
    city_weather_remote = RemoteA2aAgent(
        name=f"weather_agent_{city_slug}",
        agent_card=f"{settings.WEATHER_AGENT_URL}/.well-known/agent.json",
    )
    return LlmAgent(
        instruction=f"Ask weather_agent for weather in {city}.",
        sub_agents=[city_weather_remote],
        output_key=f"weather_{city_slug}",
    )

# ParallelAgent runs all 5 concurrently
parallel_weather = ParallelAgent(sub_agents=city_agents)

# Aggregator reads all results
aggregator_agent = LlmAgent(
    instruction="Summarise weather for all 5 cities in a table...",
)

# Sequential: parallel fetch → aggregate
root_agent = SequentialAgent(
    sub_agents=[parallel_weather, aggregator_agent],
)
```

**Important detail**: Each city needs its own `RemoteA2aAgent` instance.
An agent instance can only belong to one parent — you can't share a single
`RemoteA2aAgent` across multiple parents.

**Why SequentialAgent wraps ParallelAgent**: The parallel step runs first
(all 5 cities concurrently), stores results in state. Then the sequential
step runs the aggregator, which reads all 5 results and produces a table.

---

### 7.9 loop_agent — Polling with Exit Condition

**File: `loop_agent/agent.py` (128 lines)**

**Pattern: Start a long-running task, then poll until completion.**

```
start_task_agent → [poll_agent → exit_check_agent] × 10
                   └── LoopAgent (max_iterations=10) ──┘
```

**How it communicates with async_agent:**

```python
_async_agent_start = RemoteA2aAgent(
    name="async_agent_start",
    description="Sends a message to start a long-running task.",
    agent_card=f"{settings.ASYNC_AGENT_URL}/.well-known/agent.json",
)

_async_agent_poll = RemoteA2aAgent(
    name="async_agent_poll",
    description="Polls for task status updates.",
    agent_card=f"{settings.ASYNC_AGENT_URL}/.well-known/agent.json",
)
```

The `start_task_agent` LlmAgent delegates to `_async_agent_start` to send
a `message/send` request. The `poll_agent` LlmAgent delegates to
`_async_agent_poll` to send `tasks/get` requests.

**Exit condition:**

```python
exit_check_agent = LlmAgent(
    instruction="""
    Read poll_result from state. Respond with exactly one word:
    - "EXIT" if poll_result starts with "DONE:", "FAILED:", "CANCELED"
    - "CONTINUE" if poll_result starts with "WORKING:" or "INPUT_REQUIRED:"
    """,
    output_key="should_exit",
)
```

The LoopAgent checks `should_exit` to decide whether to continue. When
the exit_check_agent outputs "EXIT", the loop terminates.

**Bug we fixed**: The original implementation told the LLM to "POST to
async_agent" but gave it no tools or sub-agents to actually make HTTP
requests. An LLM can't make HTTP requests on its own — it needs a tool
or a RemoteA2aAgent to do that.

---

## 8. Standalone Clients

### 8.1 HTTP Client (`a2a_client/client.py`)

**Purpose**: Prove that A2A works without ADK.

```python
class A2ADemoClient:
    def __init__(self, base_url, api_key=None, bearer_token=None):
        self.base_url = base_url.rstrip("/")
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["X-API-Key"] = api_key

    async def fetch_agent_card(self) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/.well-known/agent.json")
            return resp.json()

    async def send_message(self, text, task_id=None) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}}
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.base_url + "/", json=payload)
            return resp.json()["result"]
```

**Key teaching point**: This client uses ONLY `httpx`. No `google-adk`, no
`a2a-sdk`. Just raw HTTP + JSON-RPC. This proves A2A is framework-agnostic.

**It also implements**:
- `stream_message()`: SSE streaming with `client.stream()` and `aiter_lines()`
- `get_task()`: Task polling via `tasks/get`
- `set_push_notification_config()`: Webhook registration via `tasks/pushNotificationConfig/set`

### 8.2 gRPC Client (`a2a_client/grpc_client.py`)

**Purpose**: Demonstrate the binary transport alternative (F21).

```python
class A2AGrpcClient:
    async def connect(self):
        self._channel = grpc.aio.insecure_channel(f"{host}:{port}")
        self._stub = a2a_pb2_grpc.A2AServiceStub(self._channel)

    async def send_message(self, text):
        part = a2a_pb2.Part(text=text)
        message = a2a_pb2.Message(role=a2a_pb2.ROLE_USER, content=[part])
        request = a2a_pb2.SendMessageRequest(message=message)
        response = await self._stub.SendMessage(request)
        return {"task_id": response.task.id, "status": response.task.status.state}
```

Uses `a2a-sdk`'s pre-compiled Protocol Buffer stubs. Same logical operations
(send message, stream, get task, cancel) but over HTTP/2 with binary
serialisation.

**Comparison for students:**

| Aspect | HTTP/JSON-RPC | gRPC |
|--------|---------------|------|
| Transport | HTTP/1.1 or HTTP/2 | HTTP/2 only |
| Serialisation | JSON (text) | Protobuf (binary) |
| Schema | Implicit (conventions) | Explicit (.proto file) |
| Streaming | SSE (text/event-stream) | Native server streaming |
| Browser support | Yes (fetch/XHR) | Limited (grpc-web) |
| Performance | Good | Better (smaller payloads) |

---

## 9. Webhook Server

**File: `webhook_server/main.py` (256 lines)**

A FastAPI application that receives push notifications from async_agent.

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Health check (event count) |
| POST | `/webhook` | Receive push notification |
| GET | `/events` | List all events by task_id |
| GET | `/events/{task_id}` | Events for one task |
| GET | `/events/{task_id}/latest` | Most recent event |
| DELETE | `/events` | Clear all events |

**The `/webhook` handler:**

```python
@app.post("/webhook")
async def receive_webhook(request):
    body = await request.body()
    sig = request.headers.get("X-Webhook-Signature", "")
    if sig and not verify_webhook_signature(body, sig):
        raise HTTPException(401, "Invalid signature")

    event = json.loads(body)
    event["_received_at"] = datetime.now(UTC).isoformat()
    _event_log[task_id].append(event)
    _persist_event(event)  # Write to JSONL file
    _log_event(event)      # Pretty-print to console
    return {"accepted": True}
```

**JSONL persistence**: Events are appended to `/tmp/webhook_events.jsonl`
(one JSON object per line). On startup, the server loads this file back
into memory so events survive restarts.

---

## 10. Authentication Schemes

**This is one of the most important sections for students.**

The project demonstrates four A2A authentication schemes:

### Scheme 1: No Auth (weather_agent)

The simplest — no authentication required at all. The agent card endpoint
and the JSON-RPC endpoint are both public. Suitable for internal services
behind a VPN or for public APIs.

### Scheme 2: API Key (code_agent)

```
Client → X-API-Key: demo-code-agent-key-12345 → code_agent
```

Middleware checks the header against `settings.CODE_AGENT_API_KEY`. Simple
shared secret. Discovery endpoint (`/.well-known/agent.json`) is always
public so orchestrators can find the agent.

### Scheme 3: Bearer JWT (research_agent)

```
Client → Authorization: Bearer eyJ... → research_agent
```

The token is a three-part JWT: `header.payload.signature`. Created by
`create_bearer_token()`, verified by `verify_bearer_token()`.
HMAC-SHA256 signing with a shared secret.

### Scheme 4: OAuth 2.0 (data_agent)

```
Client → Authorization: Bearer ya29... → data_agent
```

Two modes:
1. **Production**: Token is verified using `google.oauth2.id_token.verify_oauth2_token()`
2. **Demo**: Token matching `settings.CODE_AGENT_API_KEY` is accepted directly

### Cross-cutting pattern:

All agents follow the same rule:
> **Discovery is always public. Operations require auth.**

```python
if request.url.path == "/.well-known/agent.json":
    return await call_next(request)  # Always allow
# ... verify auth for everything else
```

This is essential for the A2A protocol — agents must be discoverable without
pre-shared credentials.

---

## 11. Callbacks, Guardrails, and Safety

### How Callbacks Work in ADK

```
Incoming message
    │
    ▼
[before_agent_callback]   ← Can intercept and return early
    │
    ▼
[before_model_callback]   ← Can modify the LLM request or return a cached response
    │
    ▼
    LLM Call (Gemini)
    │
    ▼
[after_model_callback]    ← Can modify/redact the LLM response
    │
    ▼
    LLM decides to call a tool
    │
    ▼
[before_tool_callback]    ← Can block the tool call (guardrails!) or return cached
    │
    ▼
    Tool Execution
    │
    ▼
[after_tool_callback]     ← Can modify tool result or cache it
    │
    ▼
Response to client
```

**Return value semantics:**
- `return None` → pass through (let normal processing continue)
- `return {...}` → intercept (use this result instead)

### Safety Guardrails in Practice (code_agent)

The code_agent chain:

```
User: "Run: import os; os.system('rm -rf /')"
    ↓
LLM: "I'll execute this code" → generates tool call with code="import os; os.system('rm -rf /')"
    ↓
[guardrail_callback_before_tool]
    ↓ Detects "os.system" in code argument
    ↓ Returns {"error": "Blocked: 'os.system' is not allowed."}
    ↓
LLM receives the error, tells user the code was blocked
```

### URL Redaction in Practice (orchestrator_agent)

```
LLM: "I routed your query to http://localhost:8001/..."
    ↓
[orchestrator_after_model]
    ↓ Detects "localhost" in response text
    ↓ Replaces with [REDACTED]
    ↓
User sees: "I routed your query to [REDACTED]/..."
```

---

## 12. Testing Strategy

### Test Structure

The project has **300 tests** across 17 test files. All tests run in
~4 seconds.

**`tests/conftest.py` — Shared fixtures:**

```python
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set safe test environment variables."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "0")  # No real GCP
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "")      # Force mock data
    monkeypatch.setenv("WEBHOOK_AUTH_TOKEN", "test-webhook-secret")
```

**Key pattern**: `autouse=True` means EVERY test gets safe mock environment
variables. No test accidentally hits real GCP services.

### Testing Approaches Used

**1. Direct function testing** (weather tools, data tools):
```python
async def test_returns_mock_data_when_no_api_key(self, monkeypatch):
    monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
    result = await tools_mod.get_weather("London")
    assert "temperature_c" in result
```

**2. FastAPI TestClient** (async_agent, webhook_server):
```python
@pytest.fixture
def client():
    from async_agent.agent import app
    return TestClient(app)

def test_agent_card_returns_200(self, client):
    resp = client.get("/.well-known/agent.json")
    assert resp.status_code == 200
```

**3. Monkeypatching settings** (auth, config):
```python
def test_signature_has_sha256_prefix(self, monkeypatch):
    monkeypatch.setattr(agent_module.settings, "WEBHOOK_AUTH_TOKEN", "test-secret")
    sig = _compute_webhook_signature(b'{"event":"test"}')
    assert sig.startswith("sha256=")
```

**4. Mocking external services** (httpx calls):
```python
async def test_network_error_returns_error_dict(self, monkeypatch):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await tools_mod.get_weather("London")
    assert "error" in result
```

### Test Categories

| Category | Files | What They Test |
|----------|-------|----------------|
| Config | test_config.py | Settings defaults, env overrides, validation |
| Auth | test_shared_auth.py | API key, Bearer JWT, HMAC verification |
| Callbacks | test_shared_callbacks.py, _extended | Logging, guardrails, caching |
| Weather | test_weather_agent.py, _extended | Mock data, API parsing, aggregation |
| Async | test_async_agent.py, _lifecycle | Task CRUD, pagination, cancel, HMAC |
| Webhook | test_webhook_server.py, _extended | Event receipt, HMAC, timestamps |
| Client | test_a2a_client.py, _extended | URL normalization, send/stream/get |
| Data | test_data_agent.py, _extended | CSV parsing, statistics, reports |
| Orchestrator | test_orchestrator_tools.py, _callbacks | Agent listing, status, redaction |

### pytest Configuration

```ini
[pytest]
asyncio_mode = auto          # Auto-detect async test functions
testpaths = tests
filterwarnings =
    ignore::DeprecationWarning
```

`asyncio_mode = auto` means any `async def test_...` function is
automatically treated as an async test — no need for `@pytest.mark.asyncio`.

---

## 13. Evaluation Framework

**File: `evals/eval_config.yaml`**

ADK provides an `adk eval` CLI that runs test cases against agents and
scores responses.

### Evaluation Criteria

```yaml
criteria:
  tool_trajectory_avg_score:
    weight: 0.4        # 40% of the total score
    threshold: 0.8     # Must score >= 0.8
  response_match_score:
    weight: 0.4        # 40% — did the response match expectations?
    threshold: 0.7
  safety_score:
    weight: 0.2        # 20% — was the response safe?
    threshold: 1.0     # Must be perfectly safe
```

### Evaluation Datasets

Each JSON file contains test cases:

```json
[
  {
    "input": "What is the weather in Paris?",
    "expected_tool_calls": ["get_weather"],
    "expected_response_contains": ["temperature", "Paris"],
    "expected_safety": "safe"
  }
]
```

**Running evals:**
```bash
adk eval ./evals/weather_eval.json --config ./evals/eval_config.yaml
```

---

## 14. Deployment

### Local Development

```bash
# Start all agents:
./scripts/start_all.sh
# → weather_agent:8001, research_agent:8002, code_agent:8003,
#   data_agent:8004, async_agent:8005, webhook_server:9000

# Start orchestrator UI:
adk web ./orchestrator_agent/
# → http://localhost:8000

# Stop all:
./scripts/stop_all.sh
```

The `start_all.sh` script:
1. Sources `.env` for environment variables
2. Creates `logs/` directory
3. Starts each agent as a background process
4. Records PIDs to `/tmp/a2a-demo.pids`
5. Uses `adk api_server --a2a` for ADK agents, `uvicorn` for custom ones

### Cloud Run Deployment

```bash
./scripts/deploy_cloud_run.sh weather_agent
```

Each agent has a Dockerfile:
```dockerfile
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "weather_agent.agent:app", "--host", "0.0.0.0", "--port", "8080"]
```

Cloud Run deployment:
1. Builds container image using Cloud Build
2. Deploys to Cloud Run with env vars from `.env`
3. Returns the service URL

### Vertex AI Agent Engine

The orchestrator can be deployed to Vertex AI Agent Engine:
```bash
./scripts/deploy_agent_engine.sh
```

This deploys the orchestrator as a managed agent that routes to Cloud Run
services.

### GCP Resources Required

```bash
# APIs enabled:
gcloud services enable aiplatform.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# GCS staging bucket:
gcloud storage buckets create gs://PROJECT-a2a-demo --location=us-central1

# Authentication:
gcloud auth application-default login
```

---

## 15. The 24 Features Matrix

| # | Feature | Description | Where Implemented |
|---|---------|-------------|-------------------|
| F1 | Agent Cards | Discovery via `/.well-known/agent.json` | All agents |
| F2 | Sync Request/Response | `message/send` JSON-RPC method | All agents |
| F3 | SSE Streaming | `message/stream` with Server-Sent Events | weather, research, async |
| F4 | Push Notifications | Webhook delivery with HMAC signature | async_agent → webhook_server |
| F5 | Task Lifecycle | States: submitted→working→completed/failed/canceled | async_agent (full state machine) |
| F6 | Multi-turn | `input-required` state + continue with `taskId` | research_agent, loop_agent |
| F7 | Extended Card | Auth-gated capabilities disclosure | research_agent (`/agents/authenticatedExtendedCard`) |
| F8 | Auth Schemes | No-auth, API Key, Bearer JWT, OAuth 2.0 | weather(none), code(key), research(jwt), data(oauth) |
| F9 | A2A Routing | Orchestrator delegates via RemoteA2aAgent | orchestrator_agent |
| F10 | Workflow Agents | SequentialAgent, ParallelAgent, LoopAgent | pipeline, parallel, loop agents |
| F11 | Agent Types | LlmAgent, SequentialAgent, ParallelAgent, LoopAgent, RemoteA2aAgent | All agents |
| F12 | Tool Types | Function tools, google_search, code_execution | weather(functions), research(search), code(executor) |
| F13 | Session State | `context.state` + `output_key` passing | pipeline_agent (3-stage state chain) |
| F14 | Memory | InMemoryMemoryService for cross-session recall | research_agent |
| F15 | Artifacts | File generation (CSV/JSON) as A2A Artifacts | data_agent (generate_csv_report) |
| F16 | Callbacks | 6 ADK callback hooks for logging/guardrails | shared/callbacks.py, orchestrator/callbacks.py |
| F17 | Safety Guardrails | Block dangerous code patterns before execution | code_agent (guardrail_callback_before_tool) |
| F18 | Evaluation | ADK eval framework with scored test cases | evals/ directory (5 datasets + config) |
| F19 | Agent Engine | Vertex AI Agent Engine deployment target | orchestrator_agent (deploy script) |
| F20 | Cloud Run | Dockerised microservice deployment | All remote agents (Dockerfiles + deploy script) |
| F21 | gRPC Transport | Protobuf/gRPC binding for A2A | a2a_client/grpc_client.py, protos/a2a_demo.proto |
| F22 | Observability | OpenTelemetry → GCP Cloud Trace | OTEL_EXPORTER_OTLP_ENDPOINT config |
| F23 | ADK Dev UI | `adk run`, `adk web`, `adk api_server` CLI | All agents |
| F24 | Interoperability | Pure httpx client (no ADK) communicates with A2A | a2a_client/client.py |

---

## 16. Live Demo Script

### Recommended demo flow (30 minutes):

**1. Agent Discovery (2 min)**
```bash
curl http://localhost:8001/.well-known/agent.json | jq '.name, .skills[].name'
```
Show the agent card. Point out skills, capabilities, auth requirements.

**2. Synchronous Message (3 min)**
```bash
curl -s -X POST http://localhost:8001/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send",
       "params":{"message":{"role":"user","parts":[{"kind":"text","text":"Weather in London?"}]}}}' | jq
```
Show the task response with status "completed" and weather data.

**3. Orchestrator Routing (5 min)**
```bash
adk web ./orchestrator_agent/
```
Open browser, ask:
- "What's the weather in Paris?" → routes to weather_agent
- "Research quantum computing advances" → routes to research_agent
- "Calculate the sum of primes below 100" → routes to code_agent

Show the orchestrator deciding which agent to call.

**4. Async Task + Push Notification (5 min)**
```bash
# Start task
TASK_ID=$(curl -s -X POST http://localhost:8005/ ... | jq -r '.result.id')
# Register webhook
curl -s -X POST http://localhost:8005/ -d '{"method":"tasks/pushNotificationConfig/set",...}'
# Watch webhook_server console for push notifications
# Poll status
curl -s -X POST http://localhost:8005/ -d '{"method":"tasks/get",...}'
```

**5. Authentication (3 min)**
```bash
# No auth on weather_agent: works
curl http://localhost:8001/.well-known/agent.json

# API key on code_agent: fails without key, works with key
curl -X POST http://localhost:8003/ -d '...'          # 403
curl -H "X-API-Key: demo-code-agent-key-12345" ...    # 200
```

**6. Pipeline Agent (5 min)**
```bash
adk run ./pipeline_agent/
# Type: "Quantum computing"
# Watch: fetch_agent → analyze_agent → report_agent
```

**7. Test Suite (2 min)**
```bash
pytest tests/ -v --tb=short
# Show: 300 passed in ~4 seconds
```

---

## 17. Key Design Decisions and Trade-offs

### 1. Custom async_agent vs ADK LlmAgent

**Decision**: async_agent uses raw FastAPI instead of ADK's `to_a2a()`.

**Why**: ADK's default handler doesn't support custom task lifecycle
management (background execution, push notifications, cancellation).
Building it from scratch shows students the full A2A protocol
implementation.

**Trade-off**: More code to maintain, but students learn the protocol
internals.

### 2. In-memory stores vs persistence

**Decision**: All state (tasks, webhooks, events) is in-memory.

**Why**: Simplicity for teaching. Production would use Redis, Firestore,
or Cloud SQL.

**Trade-off**: State is lost on restart (except webhook events which have
JSONL persistence).

### 3. Hand-rolled JWT vs library

**Decision**: `shared/auth.py` implements JWT manually.

**Why**: Students see the three-part structure (header.payload.signature)
and understand what a JWT actually is, rather than treating it as a
black box.

**Trade-off**: Not production-safe (no constant-time comparison for all
paths, no key rotation, no audience verification).

### 4. Mock data fallback

**Decision**: All tools return mock data when API keys are absent.

**Why**: The demo works out of the box without any API key configuration.
Students can see the full flow without paying for API calls.

**Trade-off**: Mock data is static and doesn't demonstrate real API
integration.

### 5. One RemoteA2aAgent per parent

**Decision**: parallel_agent creates a separate RemoteA2aAgent for each
city sub-agent.

**Why**: ADK enforces that an agent instance can only have one parent.
This is an ADK design constraint, not an A2A protocol constraint.

**Teaching point**: This is worth pointing out as a framework limitation
vs protocol limitation.

### 6. asyncio.create_task() vs BackgroundTasks

**Decision**: async_agent uses `asyncio.create_task()` for background work.

**Why**: FastAPI's `BackgroundTasks.add_task()` doesn't return the
`asyncio.Task` object, so you can't cancel it. `asyncio.create_task()`
returns the Task, which we store in `_running_tasks` for cancellation.

**Teaching point**: This was an actual bug in the original code. The
cancellation endpoint appeared to work but silently did nothing because
`_running_tasks` was always empty.

---

## 18. Common Student Questions

### Q: "Do I need GCP/Vertex AI to use A2A?"

**A**: No. A2A is an open protocol. You can build A2A agents with any
framework and deploy them anywhere. This demo uses GCP because it also
demonstrates Vertex AI Agent Engine, Cloud Run, and Google's ADK —
but the protocol itself is cloud-agnostic.

### Q: "What's the difference between a tool and a sub-agent?"

**A**: A **tool** is a Python function the LLM can call directly.
A **sub-agent** is another agent (potentially remote) that the LLM can
delegate to. Sub-agents have their own tools, instructions, and
capabilities. Tools are simple; sub-agents are complex.

### Q: "Why JSON-RPC instead of REST?"

**A**: JSON-RPC provides a consistent request/response framing. Every
A2A interaction goes to the same endpoint (`POST /`) with different
`method` values. This simplifies middleware, auth, and routing compared
to REST which would need `POST /messages`, `GET /tasks/{id}`, etc.

### Q: "Can agents call agents that call agents?"

**A**: Yes. The orchestrator calls weather_agent, which is a single hop.
But nothing prevents deeper chains. The loop_agent demonstrates a
two-hop chain: loop_agent → async_agent (via RemoteA2aAgent). In theory,
you could build arbitrarily deep delegation trees.

### Q: "How is this different from microservices?"

**A**: A2A agents ARE microservices — but with a standardised discovery
and communication protocol. Traditional microservices need custom API
contracts between each pair of services. A2A agents discover each other's
capabilities dynamically via Agent Cards and communicate using a single
universal protocol.

### Q: "What happens when an agent is down?"

**A**: The orchestrator's `get_agent_status()` tool probes the agent card
endpoint. If it returns a non-200 status or times out, the orchestrator
knows the agent is unreachable. In production, you'd add circuit breakers,
retries, and fallback routing.

### Q: "Why are there 300 tests but only 64 were mentioned in planning?"

**A**: The project has extended test suites (`*_extended.py`) that were
added during implementation. The original 64 were the core tests; the
extended tests add edge cases, pagination, timestamp validation, etc.

### Q: "How do I add a new agent?"

**A**: Follow the weather_agent pattern:
1. Create `my_agent/` directory with `__init__.py` and `agent.py`
2. Define an `AgentCard` with skills and capabilities
3. Create an `LlmAgent` with instruction, tools, and callbacks
4. Call `app = to_a2a(root_agent, port=XXXX, agent_card=card)`
5. Add the URL to `.env` and `shared/config.py`
6. Add a `RemoteA2aAgent` in orchestrator_agent
7. Write tests

---

*End of Speaker Notes*
