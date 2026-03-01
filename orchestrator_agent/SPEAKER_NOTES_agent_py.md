# Speaker Notes — `orchestrator_agent/agent.py`

> **File**: `orchestrator_agent/agent.py` (155 lines)
> **Purpose**: Root LLM agent that routes user requests to specialist A2A agents via ADK's `RemoteA2aAgent`, with pre-configured auth for each sub-agent.
> **Estimated teaching time**: 15–20 minutes
> **A2A Features covered**: F9 (A2A Routing), F11 (LlmAgent), F13 (Session State), F16 (Callbacks), F19 (Vertex AI Deployment), F22 (OpenTelemetry)

---

## Why This File Matters

This is the **hub** of the entire A2A Protocol Demo. Every user request enters
here and gets routed to the right specialist. It is the file that answers the
question: "How does one LLM agent delegate work to other agents over A2A?"

The key abstraction is `RemoteA2aAgent` — ADK's built-in class for calling
remote A2A-compliant services. The orchestrator defines five of them, wires
them as `sub_agents` to an `LlmAgent`, and lets Gemini decide which one to
invoke based on the user's message.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–37)

```python
import httpx
from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

from orchestrator_agent.callbacks import (
    orchestrator_after_model,
    orchestrator_before_model,
)
from orchestrator_agent.tools import (
    get_agent_status,
    list_available_agents,
)
from shared.auth import create_bearer_token
from shared.config import settings
```

**Explain to students:**

- `LlmAgent` is ADK's primary agent class — it wraps a Gemini model with
  tools, sub-agents, and callbacks.
- `RemoteA2aAgent` is ADK's abstraction for calling a remote A2A service. It
  takes an `agent_card` URL and, at runtime, fetches the target's Agent Card
  to discover its capabilities, supported content types, and JSON-RPC endpoint.
- `AGENT_CARD_WELL_KNOWN_PATH` is the constant `/.well-known/agent.json` —
  the standard A2A protocol discovery path (like `.well-known/openid-configuration`
  in OAuth).
- **`httpx`** is imported because the orchestrator creates pre-configured HTTP
  clients with auth headers for agents that require authentication.
- **`create_bearer_token`** from `shared.auth` generates signed JWT tokens
  for the research agent.
- Notice the clean separation: callbacks come from `orchestrator_agent.callbacks`,
  tools from `orchestrator_agent.tools`, and configuration from `shared.config`.

**Teaching moment**: `RemoteA2aAgent` is what makes A2A a protocol and not just
"one big monolith." Each specialist agent is a separate HTTP server. The
orchestrator discovers them via their Agent Card and communicates over JSON-RPC.
The agents could be written in different languages, deployed on different
infrastructure, and maintained by different teams.

---

### 2. Pre-configured HTTP Clients with Auth (lines 40–59)

```python
_A2A_TIMEOUT = httpx.Timeout(120.0)  # 2 minutes for LLM + tool calls

_code_agent_client = httpx.AsyncClient(
    headers={"X-API-Key": settings.CODE_AGENT_API_KEY},
    timeout=_A2A_TIMEOUT,
)

_research_agent_client = httpx.AsyncClient(
    headers={"Authorization": f"Bearer {create_bearer_token('orchestrator')}"},
    timeout=_A2A_TIMEOUT,
)

_data_agent_client = httpx.AsyncClient(
    headers={"Authorization": f"Bearer {settings.CODE_AGENT_API_KEY}"},
    timeout=_A2A_TIMEOUT,
)
```

**Explain to students:**

- `RemoteA2aAgent` uses httpx internally for all HTTP communication. By
  default it creates its own client with no auth headers.
- Agents that require authentication (code, research, data) need a custom
  `httpx.AsyncClient` with the appropriate headers **pre-set**.
- **120-second timeout**: The default httpx timeout is 5 seconds, which is
  too short for LLM calls that involve Google Search + Gemini inference.
  Research queries routinely take 10–20 seconds.
- Each client is configured for its agent's auth scheme:
  - Code agent: `X-API-Key` header
  - Research agent: `Bearer` JWT token signed with HMAC-SHA256
  - Data agent: `Bearer` demo token (OAuth 2.0 in production)
- Weather and async agents need no auth, so they use the default client.

**Teaching moment — why not set auth per-request?** `RemoteA2aAgent` doesn't
expose request-level hooks. The `httpx_client` parameter is the only way to
inject auth headers. This is a clean pattern: configure once at startup, every
request inherits the headers automatically.

---

### 3. Remote A2A Sub-Agent Declarations (lines 61–111)

```python
weather_agent = RemoteA2aAgent(
    name="weather_agent",
    description="Handles weather queries for any city...",
    agent_card=f"{settings.WEATHER_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

code_agent = RemoteA2aAgent(
    name="code_agent",
    description="Executes Python code in a sandboxed environment...",
    agent_card=f"{settings.CODE_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
    httpx_client=_code_agent_client,  # auth headers pre-set
)
```

Five instances are declared, one per specialist:

| Variable | Settings URL | Auth | httpx_client |
|----------|-------------|------|--------------|
| `weather_agent` | `WEATHER_AGENT_URL` | None | default |
| `research_agent` | `RESEARCH_AGENT_URL` | Bearer JWT | `_research_agent_client` |
| `code_agent` | `CODE_AGENT_URL` | API Key | `_code_agent_client` |
| `data_agent` | `DATA_AGENT_URL` | Bearer token | `_data_agent_client` |
| `async_agent` | `ASYNC_AGENT_URL` | None | default |

**Explain to students:**

- Each `RemoteA2aAgent` takes `name`, `description`, `agent_card`, and
  optionally `httpx_client` (for auth).
- The `description` is critical — it is what the LLM reads when deciding which
  sub-agent to route to. Write it as if you are explaining the agent's
  capability to a colleague. Vague descriptions lead to poor routing.
- The `agent_card` URL is built from the base URL in settings plus the
  well-known path. At runtime, ADK fetches this endpoint, parses the JSON
  Agent Card, and discovers the agent's JSON-RPC endpoint, supported skills,
  and content types.
- All five URLs default to `localhost` with sequential ports (8001–8005).
  In production, these would be Cloud Run service URLs or Kubernetes service
  DNS names.

**Teaching moment — Agent Card Discovery (F1):**

When `RemoteA2aAgent` is first used, it GETs `http://localhost:8001/.well-known/agent.json`
and receives something like:

```json
{
  "name": "weather_agent",
  "description": "Real-time weather lookup",
  "url": "http://localhost:8001",
  "capabilities": { "streaming": false, "pushNotifications": false },
  "skills": [{ "id": "get_weather", "name": "Get Weather" }]
}
```

This is how A2A achieves **runtime discovery** — the orchestrator does not need
to hard-code the capabilities of its sub-agents. It reads them from the card.

---

### 4. System Instruction (lines 115–133)

```python
_SYSTEM_INSTRUCTION = """
You are the Orchestrator Agent for the A2A Protocol Demo.

Your role is to route incoming user requests to the most appropriate specialist
agent from your team:

- **weather_agent**: Use for weather queries about any city.
- **research_agent**: Use for open-ended research requiring current information.
- **code_agent**: Use for code generation, execution, or debugging tasks.
- **data_agent**: Use for data processing, CSV generation, or analysis tasks.
- **async_agent**: Use for long-running tasks that do not require an immediate response.

You also have access to local utility tools:
- **list_available_agents**: Lists all specialist agents and their current URLs.
- **get_agent_status**: Checks if a specific agent's server is reachable.

Always be transparent about which agent you are routing to and why.
If a task spans multiple domains, break it into sub-tasks and delegate each.
"""
```

**Explain to students:**

- This instruction is the **routing logic** of the system. The LLM reads it,
  reads the user's message, and decides which sub-agent (or local tool) to
  invoke.
- The bullet list maps intents to agents. "Weather in Paris?" matches
  `weather_agent`. "Write a Python script" matches `code_agent`.
- The last line — "break it into sub-tasks and delegate each" — is how you
  get multi-agent collaboration. If a user asks "Research the weather API
  and write code to call it," the LLM can route to `research_agent` first,
  then `code_agent`.
- The local tools (`list_available_agents`, `get_agent_status`) give the LLM
  **introspection** — it can check which agents are available and whether
  they are reachable before attempting to route.

**Teaching moment**: This is "LLM-as-router." The routing is not hard-coded
`if/else` logic — it is the LLM's judgment call based on the system prompt
and user message. This makes the system flexible (it handles ambiguous
requests gracefully) but also less predictable (the LLM might misroute).
Production systems often add a confidence threshold or a fallback.

---

### 5. Root Agent Assembly (lines 135–155)

```python
root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="orchestrator",
    description="Root orchestrator that routes requests to specialist A2A agents.",
    instruction=_SYSTEM_INSTRUCTION,
    sub_agents=[
        weather_agent,
        research_agent,
        code_agent,
        data_agent,
        async_agent,
    ],
    tools=[
        list_available_agents,
        get_agent_status,
    ],
    before_model_callback=orchestrator_before_model,
    after_model_callback=orchestrator_after_model,
)
```

**Explain to students:**

- `model=settings.GEMINI_MODEL` — defaults to `gemini-2.0-flash`. Every agent
  uses the same model by default, but you could give the orchestrator a more
  capable model (e.g., `gemini-2.0-pro`) for better routing.
- `sub_agents` — the five `RemoteA2aAgent` instances. ADK presents these to
  the LLM as "available delegates." The LLM can choose to transfer control
  to any of them.
- `tools` — local Python functions. Unlike sub-agents, these execute in the
  orchestrator's own process. They give the LLM utility capabilities
  (listing agents, checking health) without making A2A calls.
- `before_model_callback` / `after_model_callback` — the orchestrator-specific
  callbacks that wrap shared logging and add safety prefix injection and URL
  redaction (see `callbacks.py` notes).
- The variable **must** be named `root_agent` — this is the convention ADK's
  CLI tools (`adk run`, `adk web`, `adk deploy`) look for when loading an
  agent module.

**Teaching moment — sub_agents vs. tools:**

| | `sub_agents` (RemoteA2aAgent) | `tools` (Python functions) |
|---|---|---|
| Execution | Remote HTTP call via A2A | Local function call |
| Discovery | Agent Card at runtime | JSON schema from type hints |
| Latency | Network round-trip | Milliseconds |
| Use case | Delegate complex tasks | Quick utility lookups |

The LLM chooses between them based on the system instruction and the
descriptions provided to each.

---

## Design Patterns to Highlight

1. **Hub-and-Spoke Architecture**: The orchestrator is the hub; specialist
   agents are spokes. All user traffic enters through the hub and is routed
   outward. This is the canonical microservices orchestration pattern.

2. **LLM-as-Router**: Instead of hard-coded routing rules, the LLM reads
   descriptions and makes routing decisions. This is flexible but requires
   careful prompt engineering to avoid misrouting.

3. **Agent Card Discovery (A2A Protocol)**: `RemoteA2aAgent` fetches
   `/.well-known/agent.json` at runtime. This decouples the orchestrator from
   the implementation details of each specialist.

4. **Separation of Concerns**: Callbacks in `callbacks.py`, tools in
   `tools.py`, configuration in `shared/config.py`. The agent file is purely
   about assembly and wiring.

5. **Convention over Configuration**: The `root_agent` variable name is a
   convention that ADK's CLI uses for module discovery. No registration or
   factory function needed.

---

## Common Student Questions

1. **"What happens if a remote agent is down?"** `RemoteA2aAgent` will fail
   when it tries to fetch the Agent Card or send the JSON-RPC request. The
   error propagates back to the LLM, which can inform the user. The
   `get_agent_status` tool lets the LLM proactively check before routing.

2. **"Can the orchestrator call two agents in parallel?"** Not with this
   setup — `LlmAgent` processes sub-agent calls sequentially. For parallel
   execution, see `parallel_agent/agent.py` which uses ADK's `ParallelAgent`.

3. **"Why five separate RemoteA2aAgent instances instead of one generic one?"**
   Each needs a distinct `name` and `description` so the LLM can differentiate
   them. The descriptions are the routing signals. A single generic agent would
   give the LLM no basis for choosing.

4. **"Could I add a sixth agent without changing this file?"** You would need
   to add a new `RemoteA2aAgent` instance and include it in `sub_agents`. The
   A2A protocol supports dynamic discovery, but ADK's `LlmAgent` requires
   sub-agents to be declared at construction time.

5. **"Why is the system instruction a string constant and not loaded from a
   file?"** For a demo, inline is clearest. In production, you might load
   prompts from a database or config file to enable A/B testing and versioning
   without code changes.

---

## Related Files

- `orchestrator_agent/callbacks.py` — Safety prefix injection and URL redaction
- `orchestrator_agent/tools.py` — `list_available_agents` and `get_agent_status`
- `shared/config.py` — Agent URLs, model name, and all environment-driven config
- `shared/callbacks.py` — Shared logging callbacks that the orchestrator callbacks wrap
- `weather_agent/agent.py` — Example of a specialist agent that this orchestrator routes to
- `tests/test_orchestrator_agent.py` — Tests for routing, callback wiring, and tool integration
