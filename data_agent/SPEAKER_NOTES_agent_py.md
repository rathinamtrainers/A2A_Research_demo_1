# Speaker Notes — `data_agent/agent.py`

> **File**: `data_agent/agent.py` (157 lines)
> **Purpose**: Data processing agent with OAuth 2.0 middleware and multi-modal Artifact generation.
> **Estimated teaching time**: 15–20 minutes
> **A2A Features covered**: F8 (OAuth 2.0), F11 (Deterministic Processing), F15 (Artifacts), F20 (Cloud Run)

---

## Why This File Matters

The data agent is the **most enterprise-grade agent** in the demo. While other
agents use simpler auth (API key, JWT, or none at all), this agent uses **OAuth
2.0 with GCP Service Account tokens** — the same auth mechanism used in
production Google Cloud services.

It also demonstrates **multi-modal input/output**: the agent accepts both
`text/plain` and `application/json` input, and can produce `text/csv` output
as downloadable Artifacts. This is the agent students should study when they
want to understand how A2A agents handle structured data and file generation.

| What makes this agent unique | Why it matters |
|------------------------------|----------------|
| OAuth 2.0 middleware | Enterprise-grade authentication |
| Multi-modal I/O (`text/csv` output) | Agents can produce files, not just text |
| Artifact generation via tools | Clean separation of data processing and file packaging |
| Dual-mode auth (GCP + demo fallback) | Graceful degradation for local development |

---

## Section-by-Section Walkthrough

### 1. Imports and Module Setup (lines 1–29)

```python
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
```

**Explain to students:**

- **`to_a2a`**: The ADK utility that wraps an agent in an A2A-compatible
  ASGI application. One function call transforms an ADK agent into a
  standards-compliant A2A server.
- **Starlette middleware**: Unlike other agents that use FastAPI dependencies
  for auth, this agent uses **raw Starlette middleware**. This is because
  OAuth 2.0 token verification needs to happen at the HTTP layer, before
  the request reaches the A2A handler. Starlette is the ASGI framework
  underneath FastAPI.
- **`AgentSkill`** and **`AgentCard`**: A2A protocol types from the `a2a`
  library. These define what the agent advertises about itself in its
  `/.well-known/agent.json` discovery endpoint.
- **Shared imports**: `logging_callback_before_model` and
  `logging_callback_after_model` come from `shared/callbacks.py`, and
  `settings` from `shared/config.py` — the same infrastructure every agent
  uses.

**Teaching moment**: Note the separation between ADK imports (`google.adk`),
A2A protocol imports (`a2a.types`), and web framework imports (`starlette`).
These are three distinct layers: agent logic, protocol definition, and HTTP
transport.

---

### 2. AgentSkill Definitions (lines 32–52)

```python
_csv_skill = AgentSkill(
    id="csv_generation",
    name="CSV Report Generation",
    description=(
        "Processes structured data and generates a downloadable CSV report "
        "as an Artifact."
    ),
    tags=["data", "csv", "report", "artifacts"],
    input_modes=["text/plain", "application/json"],
    output_modes=["text/plain", "text/csv"],
)

_stats_skill = AgentSkill(
    id="data_statistics",
    name="Data Statistics",
    description="Computes descriptive statistics (mean, median, std, etc.) on datasets.",
    tags=["data", "statistics", "analysis"],
    input_modes=["text/plain", "application/json"],
    output_modes=["text/plain", "application/json"],
)
```

**Explain to students:**

- **Skills** are the A2A protocol's way of advertising what an agent can do.
  When the orchestrator fetches this agent's Agent Card, it sees these skills
  and uses their descriptions to decide when to route tasks here.
- **`input_modes` and `output_modes`**: These are MIME types that tell callers
  what formats the agent accepts and produces. The `csv_generation` skill
  declares `text/csv` as an output mode — this signals that it can produce
  file-like output, not just text responses.
- **`tags`**: Used for discovery and filtering. An orchestrator could search
  for agents with tag `"artifacts"` to find agents that produce downloadable
  files.

**Teaching moment**: Compare the two skills. The `csv_generation` skill
outputs `text/csv` while `data_statistics` outputs `application/json`. This
is a design choice: statistics are structured data (best as JSON), while
CSV reports are tabular data (best as a CSV file). The agent advertises both
capabilities separately so callers know exactly what to expect.

---

### 3. AgentCard (lines 54–67)

```python
_AGENT_CARD = AgentCard(
    name="data_agent",
    description=(
        "Processes structured data (CSV/JSON) and returns analysis results "
        "and generated files as A2A Artifacts."
    ),
    url=settings.DATA_AGENT_URL,
    version="1.0.0",
    skills=[_csv_skill, _stats_skill],
    capabilities=AgentCapabilities(),
    default_input_modes=["text/plain", "application/json"],
    default_output_modes=["text/plain", "application/json"],
)
```

**Explain to students:**

- The **AgentCard** is the agent's identity document. It is served at
  `/.well-known/agent.json` and is the first thing any A2A client fetches
  when discovering this agent.
- **`url=settings.DATA_AGENT_URL`**: In local dev this is
  `http://localhost:8004`; in production it becomes the Cloud Run URL. The
  URL is configuration-driven, not hardcoded.
- **`default_input_modes` / `default_output_modes`**: These are the fallback
  modes when a request does not specify a particular skill. Note they include
  `application/json` — the agent can accept and return structured data
  natively.
- **`capabilities=AgentCapabilities()`**: Default capabilities with no
  streaming or push notifications. The data agent processes requests
  synchronously.

**Note the comment on line 66**: `# F8: OAuth 2.0 (GCP Service Account)
Bearer token auth`. The A2A spec allows declaring `securitySchemes` in the
Agent Card. In this demo, the auth is enforced by middleware rather than
declared in the card, but a production implementation would include the
scheme declaration.

---

### 4. LlmAgent and System Instruction (lines 69–94)

```python
_SYSTEM_INSTRUCTION = """
You are a data processing assistant.

When asked to process data:
1. Understand the format: is it CSV text, JSON, or a description of data to generate?
2. Use parse_csv_data to parse raw CSV input.
3. Use compute_statistics to calculate summary statistics.
4. Use generate_csv_report to create a formatted CSV Artifact.
5. Always return structured results with clear column descriptions.
...
"""

root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="data_agent",
    description="Processes structured data and generates CSV/JSON Artifacts.",
    instruction=_SYSTEM_INSTRUCTION,
    tools=[generate_csv_report, parse_csv_data, compute_statistics],
    before_model_callback=logging_callback_before_model,
    after_model_callback=logging_callback_after_model,
)
```

**Explain to students:**

- **`LlmAgent`**: This is an LLM-backed agent (as opposed to a `BaseAgent`
  for deterministic processing). The LLM reads the user's request, decides
  which tools to call, and synthesizes a response.
- **System instruction**: The numbered steps guide the LLM's reasoning.
  Step 1 is critical — the LLM must identify the input format before choosing
  a tool. This prevents the LLM from, say, trying to parse JSON as CSV.
- **Three tools**: `generate_csv_report`, `parse_csv_data`, `compute_statistics`.
  These are plain Python functions from `data_agent/tools.py`. ADK
  automatically generates JSON Schema descriptions from the function
  signatures and docstrings, which the LLM uses for tool selection.
- **Callbacks**: Only logging callbacks are wired in (no guardrail needed
  here since the tools do not execute arbitrary code). Compare this with
  `code_agent/agent.py` which also wires in `guardrail_callback_before_tool`.

**Teaching moment**: The system instruction mentions "Artifact" explicitly
and tells the LLM to report the Artifact ID. This is prompt engineering for
tool use — you need to tell the LLM about the output pattern so it can
communicate results to the user in a useful way.

---

### 5. A2A App Creation (line 98)

```python
app = to_a2a(root_agent, port=8004, agent_card=_AGENT_CARD)
```

**Explain to students:**

- One line creates the entire A2A server. `to_a2a()` generates:
  - `GET /.well-known/agent.json` — returns the Agent Card
  - `POST /` — the main A2A message endpoint
  - Health check endpoints for Cloud Run
- **`port=8004`**: Each agent runs on a different port (weather=8001,
  research=8002, code=8003, data=8004, async=8005).
- The `app` is a standard ASGI application. This is why we can add Starlette
  middleware to it (next section).

---

### 6. OAuth 2.0 Middleware (lines 101–157)

This is the **most important section** of the file. It demonstrates enterprise
authentication with a graceful fallback for local development.

```python
async def _oauth_middleware(request: Request, call_next):
    # Public endpoint: Agent Card discovery
    if request.url.path == "/.well-known/agent.json":
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return JSONResponse(
            {"error": "Bearer token required (OAuth 2.0 client credentials)"},
            status_code=401,
        )

    token = auth_header[len("Bearer "):]

    # Demo/test mode: accept the configured demo token directly
    demo_token = settings.CODE_AGENT_API_KEY
    if token == demo_token:
        return await call_next(request)

    # Production mode: verify via google-auth
    try:
        import google.auth.transport.requests as google_requests
        from google.oauth2 import id_token

        transport_request = google_requests.Request()
        id_token.verify_oauth2_token(token, transport_request)
        return await call_next(request)
    except ImportError:
        return JSONResponse(
            {"error": "google-auth not available for token verification"},
            status_code=503,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": f"Invalid OAuth 2.0 token: {exc}"},
            status_code=401,
        )

app.add_middleware(BaseHTTPMiddleware, dispatch=_oauth_middleware)
```

**Walk through the authentication flow:**

1. **Agent Card bypass** (line 118): The `/.well-known/agent.json` endpoint
   is **always public**. This is by design — A2A protocol requires agent
   discovery to be unauthenticated. A client needs to read the Agent Card
   to learn what auth scheme is required before it can authenticate.

2. **Bearer token extraction** (lines 121–128): Standard OAuth 2.0 pattern.
   The `Authorization` header must contain `Bearer <token>`. The
   case-insensitive check (`lower()`) handles variations like `bearer` or
   `BEARER`.

3. **Demo mode fallback** (lines 130–133): If the token matches the
   configured demo token (`settings.CODE_AGENT_API_KEY`), the request is
   allowed through. This lets developers test locally without GCP
   credentials. Note the comment "reuse for simplicity in local dev" — in
   production, you would not share API keys between agents.

4. **GCP token verification** (lines 135–148): The real OAuth 2.0 path.
   Uses `google.oauth2.id_token.verify_oauth2_token()` to validate GCP
   Service Account tokens. This function:
   - Fetches Google's public keys (cached)
   - Verifies the token's RS256 signature
   - Checks expiry, issuer, and audience claims

5. **`ImportError` handling** (lines 143–147): This is the key pattern.
   The `google-auth` library is an optional dependency. If it is not
   installed (e.g., in a minimal dev environment), the middleware returns
   503 Service Unavailable rather than crashing. This is a **graceful
   degradation** pattern.

6. **Generic error handling** (lines 149–153): Any other verification
   failure (expired token, wrong audience, malformed JWT) returns 401
   with the error message.

**Teaching moment — the `try/except ImportError` pattern:**

```python
try:
    import google.auth.transport.requests as google_requests
    from google.oauth2 import id_token
    # use them...
except ImportError:
    # handle missing dependency
```

This is a well-established Python pattern for **optional dependencies**. The
import is inside the function, not at module level. This means:
- The module can be imported even if `google-auth` is not installed.
- The dependency check happens at **runtime**, not at import time.
- You can provide a fallback (demo mode) when the dependency is unavailable.

Compare this with `tools.py`, which uses only standard library modules (`csv`,
`json`, `statistics`) and never has this problem. The architectural lesson:
keep optional dependencies in middleware/infrastructure code, not in business
logic.

---

## Design Patterns to Highlight

1. **Graceful Degradation**: The OAuth middleware works in three modes:
   real GCP tokens (production), demo tokens (development), and missing
   dependency (returns 503). The agent never crashes due to missing auth
   infrastructure.

2. **Public Discovery, Private Execution**: The Agent Card endpoint is
   always open; all other endpoints require authentication. This is the
   standard A2A protocol convention and mirrors how OAuth 2.0 discovery
   endpoints (`/.well-known/openid-configuration`) work in the broader
   ecosystem.

3. **Middleware vs. Dependency Injection**: Compare this agent's auth
   (Starlette middleware) with `code_agent` (FastAPI dependency) and
   `research_agent` (FastAPI dependency). Middleware processes every request
   at the HTTP layer; dependencies are wired into specific endpoints. Both
   are valid — middleware is better for blanket policies, dependencies for
   per-endpoint control.

4. **Skill-Based Capability Advertising**: Two skills with different output
   modes let callers choose the right capability. The orchestrator can
   request statistics (JSON) or a report (CSV) from the same agent.

5. **Optional Dependency Import**: Moving `import` statements inside
   functions enables runtime detection of optional packages without
   breaking the module import chain.

---

## Common Student Questions

1. **"Why does the demo token reuse `CODE_AGENT_API_KEY` instead of having
   its own variable?"** Pragmatism. In a demo with many agents, each with its
   own auth, adding another secret variable for every agent creates
   configuration sprawl. In production, each agent would have its own
   dedicated credentials.

2. **"Why Starlette middleware instead of FastAPI dependencies like the
   other agents?"** The `to_a2a()` function returns a Starlette/ASGI app,
   not a FastAPI app. You cannot use `Depends()` on a Starlette app. However,
   Starlette middleware works on any ASGI app, including FastAPI apps. This is
   actually the more universal approach.

3. **"What happens if `google-auth` is installed but the token is for the
   wrong audience?"** The `verify_oauth2_token()` call will raise a
   `ValueError` with a message like "Token has wrong audience." This is
   caught by the generic `except Exception` handler and returns a 401.

4. **"Why is the Agent Card endpoint public? Isn't that a security risk?"**
   No. The Agent Card is metadata — it describes what the agent does and
   what auth it requires. It does not expose any functionality. Think of it
   like a public API documentation page. You need to know the auth scheme
   before you can authenticate.

5. **"Could the LLM be replaced with deterministic logic for this agent?"**
   Yes. The docstring mentions F11 (deterministic processing). You could
   replace `LlmAgent` with a `BaseAgent` that parses the request and calls
   tools directly. The LLM adds flexibility (natural language understanding)
   at the cost of latency and non-determinism. In production, a hybrid
   approach is common: deterministic routing with LLM fallback for ambiguous
   requests.

---

## Related Files

- `data_agent/tools.py` — The three tool functions (`generate_csv_report`,
  `parse_csv_data`, `compute_statistics`) that this agent uses
- `shared/config.py` — Source of `settings.DATA_AGENT_URL`,
  `settings.GEMINI_MODEL`, `settings.CODE_AGENT_API_KEY` (demo token)
- `shared/callbacks.py` — Logging callbacks wired into the agent
- `shared/auth.py` — Contains auth utilities for other agents; compare the
  middleware approach here with the FastAPI dependency approach there
- `orchestrator_agent/agent.py` — Discovers this agent via its Agent Card URL
  and calls it as a `RemoteA2aAgent`
- `clients/a2a_client.py` — Client-side code that attaches Bearer tokens when
  calling this agent
- `tests/` — Tests for OAuth middleware behavior and Agent Card serving
