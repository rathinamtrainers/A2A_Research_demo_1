# Speaker Notes — `orchestrator_agent/tools.py`

> **File**: `orchestrator_agent/tools.py` (112 lines)
> **Purpose**: Local function tools that give the orchestrator LLM introspection into its own agent network.
> **Estimated teaching time**: 8–12 minutes
> **A2A Features covered**: F12 (Function Tools)

---

## Why This File Matters

Most A2A tutorials focus on agents calling other agents. This file shows
something subtler: giving the LLM **self-awareness** about its agent network.
The orchestrator can ask "who are my agents?" and "is the weather agent alive?"
before deciding how to route. This turns the orchestrator from a blind router
into an informed one.

Both tools are plain synchronous Python functions. ADK automatically generates
the JSON schema (for LLM function calling) from their type hints and
docstrings. No manual schema definition, no decorators, no registration — just
write a function with good types and a docstring, and ADK handles the rest.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–17)

```python
"""
Custom function tools for the Orchestrator Agent.

These tools give the orchestrator introspection capabilities:
querying which remote agents are configured and whether they are reachable.

ADK function tools are plain Python functions — ADK auto-generates the
JSON schema from type annotations and docstrings.

Reference: F12 — Function Tools.
"""

import httpx

from shared.config import settings
```

**Explain to students:**

- **`httpx`**: A modern Python HTTP client (sync and async). Used here for
  health-checking agent endpoints. It is a dependency of ADK itself, so no
  extra install is needed.
- **`settings`**: All agent URLs come from `shared.config`. The tools do not
  hard-code any URLs — they read from the centralized configuration, just like
  every other module in the project.

---

### 2. `list_available_agents()` (lines 20–59)

```python
def list_available_agents() -> dict:
    """
    Return a summary of all configured remote A2A specialist agents.

    Lists each agent's name, role, and current base URL (from environment).
    Useful for the orchestrator to remind itself about available team members.

    Returns:
        A dict with an ``agents`` list, each entry containing
        ``name``, ``description``, and ``url``.
    """
    return {
        "agents": [
            {
                "name": "weather_agent",
                "description": "Real-time weather lookup for any city",
                "url": settings.WEATHER_AGENT_URL,
            },
            {
                "name": "research_agent",
                "description": "Deep research with Google Search grounding",
                "url": settings.RESEARCH_AGENT_URL,
            },
            {
                "name": "code_agent",
                "description": "Sandboxed Python code execution",
                "url": settings.CODE_AGENT_URL,
            },
            {
                "name": "data_agent",
                "description": "Structured data processing and Artifact generation",
                "url": settings.DATA_AGENT_URL,
            },
            {
                "name": "async_agent",
                "description": "Long-running async tasks with push notifications",
                "url": settings.ASYNC_AGENT_URL,
            },
        ]
    }
```

**Explain to students:**

- **No arguments**: This function takes no parameters. ADK generates a
  zero-parameter JSON schema, and the LLM calls it when it wants to enumerate
  the available agents.
- **Return type `dict`**: ADK requires function tools to return a `dict`. The
  LLM receives the JSON-serialized dict as the tool response and can reason
  about its contents.
- **Hardcoded list**: The five agents are listed explicitly. This is
  intentional — it matches the five `RemoteA2aAgent` instances in `agent.py`.
  If you add a sixth agent, you must update both files.
- **URLs from `settings`**: The URLs reflect the current runtime configuration.
  In local dev, these will be `http://localhost:800x`. In production, they
  will be real Cloud Run service URLs.

**Teaching moment — why does the LLM need this tool?** Consider a conversation:

> **User**: "What agents do you have available?"
> **LLM**: *(calls `list_available_agents`)* "I have five specialist agents:
> weather, research, code, data, and async. Would you like me to use one?"

Without this tool, the LLM would have to rely on its system instruction alone
(which does list the agents). But the system instruction is static, while this
tool returns **live configuration** — including the actual URLs, which could
differ between environments. It gives the LLM dynamic awareness.

**Teaching moment — docstring as schema**: ADK parses the docstring to generate
the function's `description` field in the JSON schema. A clear, specific
docstring leads to better LLM tool-use decisions. Compare:

```python
# Bad: vague docstring → LLM doesn't know when to use it
def list_available_agents() -> dict:
    """Get agents."""

# Good: specific docstring → LLM knows exactly when to call it
def list_available_agents() -> dict:
    """Return a summary of all configured remote A2A specialist agents."""
```

---

### 3. `get_agent_status(agent_name)` (lines 62–112)

```python
def get_agent_status(agent_name: str) -> dict:
    """
    Check whether a named specialist agent's HTTP server is reachable.

    Sends a GET request to the agent's ``/.well-known/agent.json`` endpoint
    and reports whether it responded successfully.

    Args:
        agent_name: One of ``weather_agent``, ``research_agent``,
                    ``code_agent``, ``data_agent``, ``async_agent``.

    Returns:
        A dict with ``agent_name``, ``url``, ``reachable`` (bool),
        and an optional ``error`` message.
    """
    url_map = {
        "weather_agent": settings.WEATHER_AGENT_URL,
        "research_agent": settings.RESEARCH_AGENT_URL,
        "code_agent": settings.CODE_AGENT_URL,
        "data_agent": settings.DATA_AGENT_URL,
        "async_agent": settings.ASYNC_AGENT_URL,
    }

    base_url = url_map.get(agent_name)
    if not base_url:
        return {
            "agent_name": agent_name,
            "url": None,
            "reachable": False,
            "error": f"Unknown agent: '{agent_name}'. "
                     f"Valid names: {list(url_map.keys())}",
        }

    probe_url = f"{base_url}/.well-known/agent.json"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(probe_url)
        return {
            "agent_name": agent_name,
            "url": base_url,
            "reachable": resp.status_code == 200,
            "http_status": resp.status_code,
        }
    except httpx.RequestError as exc:
        return {
            "agent_name": agent_name,
            "url": base_url,
            "reachable": False,
            "error": str(exc),
        }
```

**Explain to students:**

- **One parameter**: `agent_name: str`. ADK reads the type hint and generates
  a JSON schema with `{"type": "string"}`. The docstring's `Args:` section
  becomes the parameter description in the schema.
- **`url_map` lookup**: Maps agent names to their base URLs from settings. This
  is a simple routing table. If the LLM passes an unknown name, the function
  returns an informative error with the list of valid names.
- **Health check mechanism**: GETs `{base_url}/.well-known/agent.json` — the
  same A2A Agent Card endpoint that `RemoteA2aAgent` uses for discovery. If
  this endpoint responds with 200, the agent is alive and serving its card.
- **`httpx.Client(timeout=5.0)`**: A 5-second timeout prevents the tool from
  hanging if an agent is unresponsive. The `with` statement ensures the HTTP
  client is properly cleaned up.
- **Error handling**: `httpx.RequestError` catches connection refused, DNS
  failure, timeout, and other network errors. The function never raises — it
  always returns a dict with `reachable: False` and an `error` message.
- **Return structure**: Always includes `agent_name`, `url`, and `reachable`.
  On success, it also includes `http_status`. On failure, it includes `error`.
  This consistent structure makes it easy for the LLM to interpret the result.

**Teaching moment — the probing pattern**: This is a classic microservices
health check. In Kubernetes, you would configure this as a liveness probe or
readiness probe. Here, the LLM itself decides when to probe — it might call
`get_agent_status("weather_agent")` before routing a weather query, or it
might skip the check for speed. The LLM has the tool; it decides when to use
it.

**Teaching moment — sync vs. async**: Both functions are synchronous (`def`,
not `async def`). ADK supports both, but sync is simpler for a demo. The 5s
timeout on `httpx.Client` means a health check blocks for at most 5 seconds.
In a production async system, you would use `httpx.AsyncClient` to avoid
blocking the event loop.

---

## How ADK Generates the JSON Schema

Show students what ADK produces from these functions. For `get_agent_status`,
the auto-generated schema looks approximately like:

```json
{
  "name": "get_agent_status",
  "description": "Check whether a named specialist agent's HTTP server is reachable.",
  "parameters": {
    "type": "object",
    "properties": {
      "agent_name": {
        "type": "string",
        "description": "One of weather_agent, research_agent, code_agent, data_agent, async_agent."
      }
    },
    "required": ["agent_name"]
  }
}
```

This schema is sent to Gemini as part of the function-calling declaration. The
LLM reads it, decides when to call the function, and provides the argument.
ADK deserializes the LLM's JSON response, calls the Python function, and
returns the result to the LLM.

**The takeaway**: Write good type hints + docstrings, and ADK does the rest.
No manual schema maintenance.

---

## Design Patterns to Highlight

1. **LLM Introspection Tools**: Giving the LLM tools to reason about its own
   infrastructure. This is a powerful pattern — the agent can diagnose issues,
   explain its capabilities, and make informed routing decisions.

2. **Graceful Degradation**: Both functions always return a dict, never raise.
   Unknown agent names get an error message; unreachable agents get
   `reachable: False`. The LLM can reason about failures instead of crashing.

3. **Convention-Based Schema Generation**: ADK's use of type hints and
   docstrings to auto-generate JSON schemas eliminates a common source of
   bugs (schema drift from implementation). The schema is always in sync
   because it is generated from the code.

4. **Configuration-Driven Discovery**: URLs are not hard-coded — they come
   from `settings`, which reads from environment variables. The same code
   works in local dev (`localhost:800x`) and production (Cloud Run URLs).

---

## Common Student Questions

1. **"Why not fetch the agent list dynamically from a service registry?"**
   Great idea for production. In a Kubernetes environment, you could query
   the API server for services with an `a2a-agent` label. For this demo,
   a hardcoded list keeps the focus on A2A protocol concepts rather than
   service discovery infrastructure.

2. **"The `list_available_agents` tool exposes internal URLs — isn't that a
   security concern?"** Yes, and that is exactly why `callbacks.py` has the
   URL redaction callback. The tool returns URLs to the LLM (it needs them
   for reasoning), but the after-model callback scrubs them before the
   response reaches the user. Defense in depth.

3. **"What if the LLM never calls these tools?"** It might not, if it can
   route purely from the system instruction. These tools are optional
   capabilities — the LLM uses them when it needs more information. You
   could prompt the LLM to always check status before routing, but that
   adds latency to every request.

4. **"Could I make `get_agent_status` return the full Agent Card JSON?"**
   Absolutely — just parse `resp.json()` and include it in the return dict.
   That would give the LLM detailed capability information (supported skills,
   content types, streaming support) to make even better routing decisions.

5. **"Why use `httpx` instead of `requests`?"** `httpx` is already a
   dependency of ADK, so there is no additional install. It also supports
   async (`httpx.AsyncClient`), making it easier to migrate to async later.

---

## Related Files

- `orchestrator_agent/agent.py` — Wires these tools into the `root_agent`'s
  `tools` list
- `orchestrator_agent/callbacks.py` — Redacts internal URLs that these tools
  might expose to the LLM
- `shared/config.py` — Source of all agent URLs used by both tools
- `tests/test_orchestrator_tools.py` — Tests for both tools including
  unknown agent names, unreachable agents, and happy-path responses
