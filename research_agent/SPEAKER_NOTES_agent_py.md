# Speaker Notes — `research_agent/agent.py`

> **File**: `research_agent/agent.py` (228 lines)
> **Purpose**: The most architecturally complex agent in the demo — combines Extended Agent Card, Bearer JWT authentication, memory services, built-in Google Search tooling, and Starlette app composition.
> **Estimated teaching time**: 25–35 minutes

---

## Why This File Matters

This is the agent you teach when students say "show me something production-like."
It touches more A2A features than any other single agent:

| Feature | ID | What It Demonstrates |
|---------|----|----------------------|
| SSE Streaming | F3 | Long research responses streamed in chunks |
| Multi-turn / input-required | F6 | Pauses for ambiguous queries |
| Extended Agent Card | F7 | Authenticated clients see premium skills |
| Bearer JWT Auth | F8 | Middleware protects all endpoints except discovery |
| Built-in Tools | F12 | `google_search` provided by ADK |
| Memory | F14 | `InMemoryMemoryService` for cross-session recall |
| Cloud Run | F20 | Dockerfile-ready deployment |

Where the weather agent is intentionally simple (no auth, function tools,
single card), the research agent layers on every enterprise concern: auth,
tiered access, memory, and app composition. It is the "capstone" agent for
the specialist tier.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–37)

```python
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from shared.auth import verify_bearer_token
from shared.config import settings
```

**Explain to students:**

- Two web frameworks appear in the imports: **Starlette** (explicit) and
  **FastAPI** (implicit, used inside `_authenticated_extended_card`). This is
  because `to_a2a()` returns a Starlette app, and we wrap it in an outer
  Starlette to add custom routes. Meanwhile, `verify_bearer_token` from
  `shared/auth.py` uses FastAPI's `HTTPAuthorizationCredentials` type.
- `google_search` is an ADK **built-in tool** (F12). It is not a Python
  function we wrote — ADK provides it with automatic Gemini grounding.
- `InMemoryMemoryService` and `InMemorySessionService` are the dev-mode
  in-memory implementations. In production you would swap these for
  `VertexAiRagMemoryService` and a persistent session store.
- `load_dotenv()` is called at module level (line 38) to ensure environment
  variables are available before `settings` is used.

---

### 2. Agent Skills and Dual Agent Cards (lines 40–88)

```python
_research_skill = AgentSkill(
    id="web_research",
    name="Web Research",
    description="Performs deep research using Google Search ...",
    tags=["research", "search", "grounding"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

_extended_skill = AgentSkill(
    id="competitive_analysis",
    name="Competitive Analysis",
    description="[PREMIUM] Deep competitive analysis ...",
    tags=["research", "competitive-analysis", "premium"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)
```

**Explain to students:**

- Two skills are defined: `web_research` (available to everyone) and
  `competitive_analysis` (premium, authenticated clients only).
- The `[PREMIUM]` prefix in the description is a convention — it signals to
  orchestrators and clients that this skill requires elevated access.

Then two `AgentCard` instances:

```python
_PUBLIC_AGENT_CARD = AgentCard(
    name="research_agent",
    url=settings.RESEARCH_AGENT_URL,
    skills=[_research_skill],
    capabilities=AgentCapabilities(streaming=True),
    ...
)

_EXTENDED_AGENT_CARD = AgentCard(
    name="research_agent",
    url=settings.RESEARCH_AGENT_URL,
    skills=[_research_skill, _extended_skill],
    capabilities=AgentCapabilities(streaming=True),
    ...
)
```

**This is the F7 Extended Agent Card pattern:**

- `_PUBLIC_AGENT_CARD` is served at `/.well-known/agent.json` (the standard
  discovery path). Any client — authenticated or not — can fetch it. It
  advertises only `web_research`.
- `_EXTENDED_AGENT_CARD` is served at `/agents/authenticatedExtendedCard` and
  requires a valid Bearer JWT. It advertises both `web_research` **and**
  `competitive_analysis`.
- The cards share the same `name`, `url`, and `version`. The only difference
  is the `skills` list and the description (which appends "(Authenticated)").

**Why two cards instead of one with a flag?** The A2A spec models capabilities
as static JSON documents. A client that fetches the card and caches it should
get a consistent view. The dual-card pattern lets unauthenticated clients see
a limited set of capabilities, while authenticated clients discover premium
skills without the public card leaking them.

**Teaching moment**: In production, you might generate the extended card
dynamically based on the caller's scopes or subscription tier. The static
dual-card approach here keeps the demo simple while demonstrating the concept.

---

### 3. System Instruction and LLM Agent (lines 90–117)

```python
_SYSTEM_INSTRUCTION = """
You are a research assistant with access to Google Search.

When a user asks a research question:
1. Use the google_search tool to gather current information.
2. Synthesise findings into a clear, structured report.
3. If the query is ambiguous or missing key parameters (e.g., "research AI"
   without specifying a focus area), respond with status input-required and
   ask the user to clarify before proceeding.
4. Always cite your sources.

For competitive analysis requests (premium tier):
- Perform multi-source deep research.
- Structure output as: Executive Summary, Key Players, Market Trends,
  SWOT Analysis, Recommendations.
"""

root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="research_agent",
    description="Deep research agent powered by Google Search grounding.",
    instruction=_SYSTEM_INSTRUCTION,
    tools=[google_search],
    before_model_callback=logging_callback_before_model,
    after_model_callback=logging_callback_after_model,
)
```

**Explain to students:**

- **F6 Multi-turn / input-required**: Instruction step 3 tells the LLM to
  respond with `input-required` status when the query is ambiguous. The LLM
  does not set A2A task status directly — instead, ADK detects the LLM's
  response and maps it to the A2A `input-required` task state. The client then
  knows to prompt the user for clarification and send a follow-up message.
- **F12 Built-in tool**: `tools=[google_search]` — this is the entire tool
  setup. No function definition, no schema, no API key management. ADK's
  `google_search` is a first-class built-in that provides real-time web search
  with Gemini grounding. Compare this to the weather agent, where we wrote
  custom Python functions as tools.
- **Callbacks**: Only logging callbacks are wired here (no guardrails, no
  cache). The research agent's tool (`google_search`) is a built-in that
  doesn't benefit from code-safety guardrails — those are for the code agent.
- **Competitive analysis prompt**: The system instruction handles both the
  basic `web_research` skill and the premium `competitive_analysis` skill with
  a single LLM agent. The skill distinction is at the **card level** (what
  clients can discover), not at the agent logic level. The LLM can do both —
  the card just controls who knows about it.

**Teaching moment**: This is an important architectural pattern — the extended
card gates **discovery**, not **execution**. An unauthenticated client that
somehow sends a competitive analysis request would still get a response,
because the LLM can handle it. The security boundary is at the middleware
level (F8), not the prompt level. True premium enforcement would require the
agent to check authentication state before performing premium tasks.

---

### 4. Runner with Memory Service (lines 119–130)

```python
_memory_service = InMemoryMemoryService()

_runner = Runner(
    app_name=root_agent.name,
    agent=root_agent,
    session_service=InMemorySessionService(),
    memory_service=_memory_service,
)
```

**Explain to students:**

- **F14 Memory**: This is the only agent in the demo that uses a memory
  service. `InMemoryMemoryService` stores key facts extracted from
  conversations so the agent can recall them in future sessions.
- **Why a separate `Runner`?** Without an explicit runner, `to_a2a()` creates
  its own internally with default services (no memory). By constructing the
  runner ourselves, we inject `_memory_service` and then pass the runner to
  `to_a2a()`.
- **`InMemorySessionService`** manages session state (conversation history)
  within a single process. Combined with memory service, this gives the agent
  both short-term context (session) and long-term recall (memory).

**Session vs Memory — explain the difference:**

| Concept | Scope | Persistence | ADK Class |
|---------|-------|-------------|-----------|
| **Session** | Single conversation | Lives until session ends | `InMemorySessionService` |
| **Memory** | Cross-session | Persists across sessions | `InMemoryMemoryService` |

In production, you would replace `InMemoryMemoryService` with
`VertexAiRagMemoryService`, which uses Vertex AI RAG for persistent,
retrieval-augmented memory across sessions and even across agent restarts.

**Teaching moment**: Both services are "InMemory" here, meaning all state is
lost when the process restarts. This is fine for demos but highlights why
production agents need persistent backends. Ask students: "What happens to
the research agent's memory when you redeploy to Cloud Run?"

---

### 5. A2A App Creation (lines 132–134)

```python
_a2a_app = to_a2a(root_agent, port=8002, agent_card=_PUBLIC_AGENT_CARD, runner=_runner)
```

**Explain to students:**

- `to_a2a()` is the ADK function that converts an agent into an A2A-compliant
  Starlette web application. It wires up:
  - `/.well-known/agent.json` — serves the `_PUBLIC_AGENT_CARD`
  - JSON-RPC endpoint at `/` — handles `message/send`, `message/stream`,
    `tasks/get`, etc.
- `port=8002` sets the port hint (used in local dev).
- `agent_card=_PUBLIC_AGENT_CARD` overrides the auto-generated card with our
  custom card that includes streaming capability.
- `runner=_runner` passes our pre-configured runner with memory service.

**Key detail**: The result `_a2a_app` is a **Starlette** app, not the final
app. We will wrap it in an outer Starlette to add the extended card route.
This is the app composition pattern (covered in section 8).

---

### 6. Authenticated Extended Card Endpoint (lines 136–168)

```python
async def _authenticated_extended_card(request: Request) -> Response:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return JSONResponse({"error": "Bearer token required"}, status_code=401)
    token = auth_header[len("Bearer "):]

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    creds = HTTPAuthorizationCredentials(scheme="bearer", credentials=token)
    try:
        verify_bearer_token(credentials=creds)
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    return JSONResponse(_EXTENDED_AGENT_CARD.model_dump(exclude_none=True))
```

**Explain to students:**

- This is a **plain Starlette route handler** (not a FastAPI endpoint). It
  takes a `Request` and returns a `Response`.
- **Why inline FastAPI imports?** `verify_bearer_token` expects a FastAPI
  `HTTPAuthorizationCredentials` object (because it was written as a FastAPI
  dependency). Since this handler lives in a Starlette context (no dependency
  injection), we manually construct the credentials object and call the
  function directly.
- The lazy `from fastapi import ...` on lines 158-159 is inside the function
  body rather than at the top of the file. This is an intentional choice to
  keep the top-level imports clean and make the FastAPI dependency obvious at
  the point of use.
- `_EXTENDED_AGENT_CARD.model_dump(exclude_none=True)` serializes the Pydantic
  model to a dict, dropping `None` fields for a cleaner JSON response.

**The flow:**
1. Client sends `GET /agents/authenticatedExtendedCard` with
   `Authorization: Bearer <jwt>`.
2. Handler extracts the token, wraps it in `HTTPAuthorizationCredentials`.
3. Calls `verify_bearer_token()` from `shared/auth.py` — validates structure,
   signature, and expiry.
4. On success, returns the extended card (both skills).
5. On failure, returns 401 with the error detail.

**Teaching moment**: This endpoint manages its own auth independently from the
middleware (section 7). The middleware's `_OPEN_PATHS` set includes this path,
so the middleware skips it. This is intentional — the endpoint needs to
distinguish between "no token" (401) and "valid token" (200 with extended
card), while the middleware would just block all unauthenticated requests.

---

### 7. Bearer Auth Middleware (lines 170–207)

```python
_OPEN_PATHS = frozenset({
    "/.well-known/agent.json",
    "/agents/authenticatedExtendedCard",
})

async def _bearer_auth_middleware(request: Request, call_next):
    if request.url.path in _OPEN_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return JSONResponse({"error": "Bearer token required"}, status_code=401)
    token = auth_header[len("Bearer "):]

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    creds = HTTPAuthorizationCredentials(scheme="bearer", credentials=token)
    try:
        verify_bearer_token(credentials=creds)
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    return await call_next(request)
```

**Explain to students:**

- **F8 Bearer JWT Authentication**: This middleware wraps the entire Starlette
  app. Every request passes through it before reaching any route handler.
- **`_OPEN_PATHS`**: A `frozenset` of paths that bypass auth. Two paths are
  open:
  1. `/.well-known/agent.json` — A2A discovery must always be public. Without
     this, clients could never discover the agent in the first place.
  2. `/agents/authenticatedExtendedCard` — manages its own auth (see section 6).
- **`frozenset`**: Used instead of a regular `set` because it is immutable and
  hashable. The immutability is a defensive choice — the open paths should
  never change at runtime.
- The middleware function follows the standard Starlette middleware pattern:
  `async def dispatch(request, call_next)`. It either short-circuits with a
  401 response or calls `call_next(request)` to pass the request downstream.

**Duplicate code observation**: The token extraction and verification logic in
the middleware (lines 190-206) is nearly identical to the extended card
endpoint (lines 150-165). Ask students: "How would you refactor this?" A
helper function like `_extract_and_verify_token(request) -> dict | JSONResponse`
would eliminate the duplication.

**Teaching moment — middleware vs dependency injection:**

| Approach | Where | Best For |
|----------|-------|----------|
| Middleware | Wraps all routes | Global auth enforcement |
| FastAPI `Depends()` | Per-endpoint | Granular per-route auth |

The research agent uses middleware because **most** endpoints need auth. The
code agent uses `Depends(verify_api_key)` because it has fewer concerns. Both
are valid patterns.

---

### 8. Starlette App Composition (lines 210–228)

```python
app = Starlette(
    routes=[
        Route(
            "/agents/authenticatedExtendedCard",
            _authenticated_extended_card,
            methods=["GET"],
        ),
        Mount("/", app=_a2a_app),
    ]
)

app.add_middleware(BaseHTTPMiddleware, dispatch=_bearer_auth_middleware)
```

**Explain to students:**

- This is the most architecturally interesting part of the file. We are
  **composing two Starlette apps** — an outer app with custom routes and an
  inner app (`_a2a_app`) generated by `to_a2a()`.
- **Why not just add the route to `_a2a_app`?** Because `to_a2a()` returns a
  complete app with its own routing. We cannot easily inject routes into it.
  Instead, we create an outer Starlette app that:
  1. Handles `/agents/authenticatedExtendedCard` directly.
  2. Delegates everything else to `_a2a_app` via `Mount("/", app=_a2a_app)`.
- **Route order matters**: The explicit `Route` for the extended card path is
  listed **before** the catch-all `Mount("/")`. Starlette matches routes in
  order, so requests to `/agents/authenticatedExtendedCard` are handled by our
  custom handler, not by the inner A2A app.
- **`app.add_middleware(BaseHTTPMiddleware, dispatch=_bearer_auth_middleware)`**:
  The middleware is added **after** the app is constructed. Starlette rebuilds
  its middleware stack lazily, so this works correctly. The middleware wraps
  **both** the custom route and the mounted A2A app.

**Visualize the request flow for students:**

```
Incoming request
  │
  ▼
Bearer Auth Middleware (F8)
  │
  ├── path in _OPEN_PATHS? → pass through
  └── else → verify JWT → 401 or pass through
        │
        ▼
  Outer Starlette router
  │
  ├── /agents/authenticatedExtendedCard → _authenticated_extended_card()
  └── /* (everything else) → Mount("/") → _a2a_app
        │
        ├── /.well-known/agent.json → public agent card
        └── / (JSON-RPC) → message/send, message/stream, etc.
```

**Teaching moment**: This composition pattern is powerful but can be confusing.
The key insight is that `Mount` is Starlette's equivalent of a reverse proxy
at the application level. The inner app has no idea it is mounted — it handles
requests as if it were the root app.

---

## Design Patterns to Highlight

1. **Layered Discovery (Extended Agent Card)**: Public clients see basic
   capabilities; authenticated clients discover premium skills. This mirrors
   real-world API tiers (free vs. paid plans) without exposing internal
   implementation details.

2. **Middleware-Based Security**: Authentication is enforced at the transport
   layer (HTTP middleware), not at the application layer. The agent logic never
   checks auth — it simply handles requests that have already passed the
   middleware gate. This is separation of concerns at work.

3. **App Composition via Mount**: Wrapping a generated app (`to_a2a()`) in an
   outer app with additional routes is a clean way to extend framework-generated
   code without modifying it. This pattern is reusable anywhere ADK's `to_a2a()`
   is involved.

4. **Explicit Runner Injection**: By constructing the `Runner` manually with
   specific services (memory, session), we gain control over the agent's
   runtime behavior without modifying `to_a2a()` internals.

5. **Open-Path Allowlist**: Using a `frozenset` of paths that bypass auth is a
   common pattern in middleware-based security. It defaults to "deny all" and
   explicitly allows specific exceptions — the safest default.

6. **Single LLM, Multiple Skills**: The same `LlmAgent` handles both basic
   research and premium competitive analysis. The skill distinction is a
   discovery-level concern (Agent Card), not an execution-level concern (LLM
   prompt). This keeps the agent simple while supporting tiered access.

---

## Common Student Questions

1. **"Why does discovery (`/.well-known/agent.json`) need to be public?"**
   The A2A Protocol requires agent cards to be discoverable without
   authentication. A client that doesn't know what auth scheme an agent
   requires must be able to fetch the card first to learn the auth
   requirements. If discovery required auth, you'd have a chicken-and-egg
   problem: how do you authenticate if you don't know the auth scheme?

2. **"Can an unauthenticated client still send a competitive analysis
   request?"** No — the middleware (F8) blocks all unauthenticated requests to
   the JSON-RPC endpoint. But the security boundary is at the middleware, not
   the LLM. If you somehow bypassed the middleware, the LLM would happily do
   competitive analysis. For true defense-in-depth, the agent logic should
   also verify the caller's tier.

3. **"Why use `InMemoryMemoryService` instead of a database?"** For the demo,
   in-memory is sufficient and requires no infrastructure. In production, you
   would use `VertexAiRagMemoryService` (backed by Vertex AI Search) or a
   custom implementation backed by a database. The key point is that ADK's
   `Runner` accepts any implementation of the memory service interface.

4. **"What is the difference between `google_search` and writing a custom
   search tool?"** ADK's `google_search` is a built-in tool that uses Gemini's
   native search grounding. The LLM can search the web and cite sources
   without any API key management or result parsing on our part. A custom tool
   would give you more control (specific APIs, result filtering) but requires
   more code and maintenance.

5. **"Why are there `from fastapi import ...` statements inside function
   bodies?"** The `verify_bearer_token` function was designed as a FastAPI
   dependency (using `HTTPAuthorizationCredentials`). Since this agent uses
   Starlette (not FastAPI) for its routes, we need to construct the
   credentials object manually. The imports are inline to make this adapter
   pattern explicit and to keep top-level imports clean.

6. **"How does `input-required` (F6) actually work?"** The system instruction
   tells the LLM to ask for clarification when queries are ambiguous. When
   the LLM responds with a clarifying question, ADK detects this and sets the
   A2A task status to `input-required`. The client sees this status and knows
   to prompt the user for more information, then send a follow-up message on
   the same task. This creates a multi-turn conversation within a single task.

7. **"Why compose two Starlette apps instead of using FastAPI?"** The `to_a2a()`
   function returns a Starlette app, not a FastAPI app. We could convert it to
   FastAPI, but that would add unnecessary complexity. Starlette's `Mount`
   gives us clean composition without changing the inner app. FastAPI is built
   on Starlette anyway, so we're not losing any capability.

---

## Related Files

- `shared/auth.py` — Provides `verify_bearer_token()` used by both the
  middleware and the extended card endpoint
- `shared/config.py` — Source of `RESEARCH_AGENT_URL`, `GEMINI_MODEL`,
  `RESEARCH_AGENT_JWT_SECRET`
- `shared/callbacks.py` — Provides `logging_callback_before_model` and
  `logging_callback_after_model` wired into the `LlmAgent`
- `research_agent/__init__.py` — Package docstring listing all demonstrated
  features (F3, F6, F7, F8, F12, F14, F20)
- `research_agent/Dockerfile` — Cloud Run deployment configuration; runs
  `uvicorn research_agent.agent:app`
- `orchestrator_agent/agent.py` — Creates a `RemoteA2aAgent` pointing to the
  research agent's card URL for delegation
- `clients/a2a_client.py` — Client-side code that attaches Bearer tokens when
  calling the research agent
