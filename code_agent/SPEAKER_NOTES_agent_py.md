# Speaker Notes — `code_agent/agent.py`

> **File**: `code_agent/agent.py` (118 lines)
> **Purpose**: A2A-compliant code execution agent using Gemini's native sandboxed Python executor.
> **Estimated teaching time**: 15–20 minutes
> **A2A Features covered**: F8 (API Key auth), F12 (Gemini code_execution), F17 (Safety guardrails), F20 (Cloud Run deployment)

---

## Why This File Matters

This is the best file in the project for teaching **defense in depth**. It
layers three independent safety mechanisms — a system instruction, a callback
guardrail, and a sandboxed executor — so that if any single layer fails, the
others still protect the system. It also demonstrates the simplest possible
API Key authentication, and Gemini's built-in code execution capability that
removes the need for a custom tool function entirely.

At only 118 lines, it packs four A2A features into a single readable file.
Use it as your go-to example when students ask "how does a real agent get
wired up end to end?"

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–27)

```python
"""
Code Agent — Sandboxed Python code execution via Gemini code_execution tool.

Demonstrates:
  F8  — API Key authentication (X-API-Key header)
  F12 — Gemini built-in code_execution tool (BuiltInCodeExecutor)
  F17 — Safety guardrails blocking dangerous code patterns
  F20 — Cloud Run deployment
"""

from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from starlette.middleware.base import BaseHTTPMiddleware
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from shared.callbacks import (
    guardrail_callback_before_tool,
    logging_callback_after_tool,
    logging_callback_before_tool,
)
from shared.config import settings
```

**Explain to students:**

- **`BuiltInCodeExecutor`** is the star import. It comes from
  `google.adk.code_executors`, not from a custom tool module. This is Gemini's
  native sandboxed Python execution — the model itself runs code inside
  Google's infrastructure.
- **Starlette, not FastAPI**: The middleware uses `BaseHTTPMiddleware` from
  Starlette directly. `to_a2a()` returns a Starlette-compatible ASGI app, so
  middleware at the Starlette level works regardless of whether the underlying
  framework is FastAPI or pure Starlette.
- **Selective callback imports**: The agent imports `guardrail_callback_before_tool`
  for safety and two logging callbacks for observability. It does not import
  the cache callbacks — code execution results should not be cached (they may
  have side effects, and users expect fresh execution).

---

### 2. AgentSkill Definitions (lines 32–52)

```python
_code_skill = AgentSkill(
    id="code_execution",
    name="Python Code Execution",
    description=(
        "Generates and executes Python code in a sandboxed environment. "
        "Returns code, stdout, stderr, and any generated files."
    ),
    tags=["code", "execution", "python"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

_debug_skill = AgentSkill(
    id="code_debug",
    name="Code Debugging",
    description="Analyses Python code for bugs and suggests fixes.",
    tags=["code", "debug", "python"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)
```

**Explain to students:**

- **Two skills, one agent**: The A2A protocol lets an agent advertise multiple
  capabilities. The orchestrator reads these skills from the Agent Card and
  decides which agent to delegate to based on the `description` and `tags`.
- **`code_execution` vs `code_debug`**: These are semantically distinct. The
  first runs code and returns output; the second analyses code without
  necessarily executing it. In practice, both flow through the same
  `BuiltInCodeExecutor`, but the distinction helps the orchestrator route
  requests correctly.
- **`input_modes` / `output_modes`**: Both use `text/plain`. Code execution
  could in theory return `image/png` (e.g., matplotlib plots), but this demo
  keeps it simple with text-only.
- **`tags`**: Used for skill discovery and filtering. The orchestrator can
  search for agents with `tags=["code"]` when it needs code-related help.

**Teaching moment**: Skills are the A2A protocol's answer to "how does an
orchestrator know what an agent can do?" Without skills, the orchestrator
would need hardcoded knowledge of each agent's capabilities.

---

### 3. AgentCard (lines 54–64)

```python
_AGENT_CARD = AgentCard(
    name="code_agent",
    description="Executes Python code safely in a Gemini-managed sandbox.",
    url=settings.CODE_AGENT_URL,
    version="1.0.0",
    skills=[_code_skill, _debug_skill],
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    # F8: API Key auth required (X-API-Key header)
)
```

**Explain to students:**

- **`url=settings.CODE_AGENT_URL`**: Defaults to `http://localhost:8003`. In
  production on Cloud Run, this is overridden via environment variable to the
  Cloud Run service URL.
- **`capabilities=AgentCapabilities(streaming=True)`**: Advertises that this
  agent supports streaming responses. The orchestrator or client can choose to
  use SSE (Server-Sent Events) for real-time output as the code executes.
- **`version="1.0.0"`**: Semantic versioning for the agent. Allows clients to
  detect breaking changes.
- **Port 8003**: Each agent in the demo runs on a unique port. The port
  mapping is: weather=8001, research=8002, **code=8003**, data=8004, async=8005.

**Note the comment about F8**: The Agent Card does not directly enforce
authentication. In a full A2A implementation, the `securitySchemes` field
would advertise the required auth. Here, authentication is enforced at the
middleware layer (see section 6 below).

---

### 4. System Instruction (lines 70–80)

```python
_SYSTEM_INSTRUCTION = """
You are a code execution assistant. When asked to run code:
1. Write clean, correct Python code to solve the problem.
2. Execute it using the code execution tool.
3. Return the output along with a clear explanation.

SAFETY RULES (enforced by guardrail callbacks):
- Never use os.system, subprocess, or shutil.rmtree.
- Never use exec() or eval() on user-provided strings.
- Never open files outside the sandbox working directory.
"""
```

**Explain to students:**

- **First line of defense**: The system instruction tells the model what it
  should and should not do. LLMs generally follow system instructions, but
  they can be jailbroken. This is why the instruction alone is insufficient.
- **"enforced by guardrail callbacks"**: This phrase is deliberately included
  in the instruction. It serves two purposes: (a) it reinforces to the model
  that these rules are non-negotiable, and (b) it documents for developers
  that the rules are not just suggestions — they are backed by programmatic
  enforcement.
- **The three numbered steps** guide the model to produce structured output:
  code first, then execution, then explanation. This makes the agent's
  responses predictable and easy to parse.

**Teaching moment — the three layers of defense**:

```
Layer 1: System instruction    → "Please don't do dangerous things"
Layer 2: Guardrail callback    → Programmatically blocks dangerous patterns
Layer 3: Sandboxed executor    → Even if code runs, it can't escape the sandbox
```

Each layer catches what the previous one missed. The system instruction is
probabilistic (LLMs can be tricked); the guardrail is deterministic but uses
string matching (can be bypassed with obfuscation); the sandbox is enforced by
the runtime (hardest to escape). This is defense in depth.

---

### 5. LlmAgent Construction (lines 82–90)

```python
root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="code_agent",
    description="Executes Python code in a sandboxed environment.",
    instruction=_SYSTEM_INSTRUCTION,
    code_executor=BuiltInCodeExecutor(),  # F12 — Gemini built-in code execution
    before_tool_callback=guardrail_callback_before_tool,  # F17 — Safety guardrail
    after_tool_callback=logging_callback_after_tool,
)
```

**Explain to students:**

- **`code_executor=BuiltInCodeExecutor()`**: This is the key line. Instead of
  defining a custom `@tool` function that spawns a subprocess to run Python,
  `BuiltInCodeExecutor` tells Gemini to use its **native code execution
  capability**. The model generates code, executes it in Google's server-side
  sandbox, and returns the result — all within a single API call.

- **`BuiltInCodeExecutor` vs a custom tool**: This is one of the most
  important teaching points in the project. Compare:

  | Approach | Sandbox | Latency | Setup |
  |----------|---------|---------|-------|
  | `BuiltInCodeExecutor` | Google-managed, zero config | Single API round-trip | One line |
  | Custom `@tool` with `subprocess` | You manage (Docker, gVisor, nsjail) | Extra round-trip per execution | Complex |

  `BuiltInCodeExecutor` is the right choice when you trust Gemini's sandbox
  and don't need access to local files or custom packages. For agents that
  need to interact with the local filesystem or use specific Python libraries,
  you would use a custom tool instead.

- **`before_tool_callback=guardrail_callback_before_tool`**: Wires in the
  safety guardrail from `shared/callbacks.py`. This fires before every tool
  call (including the code execution tool) and checks for dangerous patterns
  like `os.system`, `subprocess`, `exec(`, etc.

- **`after_tool_callback=logging_callback_after_tool`**: Logs tool results
  for observability. Note there is no `before_model_callback` or
  `after_model_callback` here — the code agent keeps its callback set minimal.

- **No `tools=[]` parameter**: Unlike other agents that pass a list of
  `@tool` functions, this agent has no explicit tools. `BuiltInCodeExecutor`
  is not a tool — it is a code executor, a separate concept in ADK. The model
  automatically gets access to a `code_execution` capability when a code
  executor is set.

**Common confusion**: Students often ask "where is the tool?" The answer is
that `BuiltInCodeExecutor` injects the code execution capability directly into
the model configuration. There is no separate tool function to write.

---

### 6. A2A App and API Key Middleware (lines 92–118)

```python
app = to_a2a(root_agent, port=8003, agent_card=_AGENT_CARD)


async def _api_key_middleware(request: Request, call_next):
    """
    Middleware that enforces X-API-Key authentication (F8).
    The ``/.well-known/agent.json`` discovery endpoint is always public.
    """
    # Allow discovery endpoint without auth
    if request.url.path == "/.well-known/agent.json":
        return await call_next(request)

    api_key = request.headers.get("X-API-Key", "")
    if not api_key or api_key != settings.CODE_AGENT_API_KEY:
        return JSONResponse(
            {"error": "Invalid or missing API key"},
            status_code=403,
        )
    return await call_next(request)


app.add_middleware(BaseHTTPMiddleware, dispatch=_api_key_middleware)
```

**Explain to students:**

- **`to_a2a()`**: The ADK utility that wraps an `LlmAgent` into a
  fully-functional A2A server. It creates:
  - `/.well-known/agent.json` — the Agent Card discovery endpoint
  - `/` — the main A2A message endpoint (POST)
  - SSE streaming support (because `capabilities.streaming=True`)

- **Discovery endpoint exemption**: Line 105 checks if the request path is
  `/.well-known/agent.json`. If so, the request passes through without auth.
  This is critical — the orchestrator needs to fetch the Agent Card to
  discover the agent's capabilities **before** it knows what auth scheme to
  use. The discovery endpoint must always be public.

- **API Key validation**: Lines 108–113 implement the simplest possible auth
  scheme. The client sends `X-API-Key: <value>` in the request header; the
  middleware compares it to `settings.CODE_AGENT_API_KEY` (default:
  `demo-code-agent-key-12345`).

- **`app.add_middleware()`**: Middleware is added **after** `to_a2a()` creates
  the app. This means middleware wraps all routes, including the A2A endpoints.
  The ordering matters — middleware added last executes first (outermost in the
  middleware stack).

**Teaching moment — middleware vs dependency injection:**

The code agent uses Starlette middleware for auth. The `shared/auth.py` module
provides FastAPI dependency-injection functions (`verify_api_key`). Both
approaches work, and this agent deliberately uses middleware to show the
alternative pattern:

| Approach | Scope | When to use |
|----------|-------|-------------|
| Middleware | All routes (global) | When every endpoint needs the same auth |
| Dependency injection | Per-route | When different routes need different auth |

The middleware approach is simpler for this agent since every endpoint (except
discovery) needs the same API key check.

**Security note**: The `!=` comparison on line 109 is a plain string
comparison, vulnerable to timing attacks. Production code should use
`hmac.compare_digest()`. See `shared/auth.py` for the correct pattern.

---

## Design Patterns to Highlight

1. **Defense in Depth**: Three independent safety layers — system instruction
   (probabilistic), guardrail callback (deterministic string matching), and
   sandboxed executor (runtime isolation). Each catches what the previous
   layer missed.

2. **Convention over Configuration**: `BuiltInCodeExecutor()` requires zero
   configuration. No container images, no sandbox setup, no security policies.
   The sandbox is Gemini's responsibility. One line replaces what would
   otherwise be hundreds of lines of infrastructure code.

3. **Separation of Concerns**: Authentication (middleware), agent logic
   (LlmAgent), safety (callback), and execution (code executor) are each
   handled by a different component. Changing one does not require changing
   the others.

4. **Middleware Pattern**: HTTP-level concerns (auth) are separated from
   application-level concerns (agent behavior) via Starlette middleware. The
   agent itself has no knowledge of authentication.

5. **Agent Card as Service Contract**: The `AgentCard` with its skills,
   capabilities, and input/output modes serves as a machine-readable API
   contract. Other agents can discover and understand this agent without any
   out-of-band documentation.

---

## Common Student Questions

1. **"Why use `BuiltInCodeExecutor` instead of writing a custom tool?"**
   `BuiltInCodeExecutor` runs code inside Gemini's own sandbox — you get
   Google-managed security with zero infrastructure. A custom tool is needed
   only when you must access local files, use specific Python packages not
   available in Gemini's sandbox, or control the execution environment
   directly. For this demo, the built-in executor is the right choice.

2. **"Can the guardrail callback catch everything?"** No. It uses simple
   string matching, which can be bypassed with obfuscation (e.g.,
   `getattr(os, 'system')` instead of `os.system`). That is exactly why the
   sandbox is the third layer — even if the guardrail misses something, the
   sandboxed executor prevents real damage. In production, you would add
   AST-based analysis or a dedicated code scanning service.

3. **"Why is the discovery endpoint public?"** The A2A protocol requires it.
   An orchestrator needs to fetch `/.well-known/agent.json` to learn what
   the agent can do and what auth scheme it requires. If discovery itself
   required auth, you would have a chicken-and-egg problem: you cannot
   authenticate without knowing the scheme, and you cannot know the scheme
   without authenticating.

4. **"What happens if the API key is wrong?"** The middleware returns a 403
   JSON response (`{"error": "Invalid or missing API key"}`) and the request
   never reaches the agent. The LLM is never invoked, so there is no token
   cost for rejected requests.

5. **"Where does the code actually run?"** Inside Google's infrastructure,
   not on this server. When `BuiltInCodeExecutor` is used, the code is sent
   to Gemini as part of the model request. Gemini executes it in an isolated
   sandbox and returns the output. The agent server itself never runs
   untrusted code.

6. **"Why are there two skills but no two separate tools?"** Skills describe
   **what the agent can do** (a capability advertisement for the orchestrator).
   Tools describe **how the agent does it** (actual executable functions). The
   agent has one executor that handles both code execution and code debugging.
   The skill distinction helps the orchestrator make routing decisions.

---

## Related Files

- `shared/callbacks.py` — Defines `guardrail_callback_before_tool` (F17) and
  the logging callbacks used by this agent
- `shared/config.py` — Source of `settings.GEMINI_MODEL`, `CODE_AGENT_URL`,
  and `CODE_AGENT_API_KEY`
- `shared/auth.py` — Alternative auth implementation using FastAPI dependency
  injection (compare with the middleware approach here)
- `code_agent/Dockerfile` — Cloud Run deployment container (F20), runs
  `uvicorn code_agent.agent:app`
- `orchestrator_agent/agent.py` — Calls this agent via `RemoteA2aAgent` with
  the API key attached
- `clients/a2a_client.py` — Client-side code that sends `X-API-Key` header
  when contacting this agent
- `tests/test_shared_callbacks.py` — Tests for the guardrail callback that
  this agent depends on
