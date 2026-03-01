# Speaker Notes — `weather_agent/agent.py`

> **File**: `weather_agent/agent.py` (88 lines)
> **Purpose**: Creates the weather agent A2A server with AgentCard, LlmAgent, and FastAPI wrapping.
> **Estimated teaching time**: 15–20 minutes
> **A2A Features covered**: F1 (AgentCard), F2 (Sync), F3 (Streaming), F8 (No Auth), F12 (Function Tools), F20 (Cloud Run)

---

## Why This File Matters

This is the **simplest complete A2A agent** in the demo. It is the best file to
open first when teaching the A2A protocol, because it demonstrates the full
lifecycle in under 90 lines:

1. Define skills (what the agent advertises it can do)
2. Create an AgentCard (the agent's public identity and capabilities)
3. Build an LlmAgent (the actual Gemini-powered logic)
4. Wrap it as a FastAPI app with `to_a2a()` (the A2A server)

Every other agent in the project follows the same four-step pattern. Once
students understand this file, they have the blueprint for all the rest.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–27)

```python
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from shared.callbacks import logging_callback_before_tool, logging_callback_after_tool
from shared.config import settings
from weather_agent.tools import get_weather, get_forecast
```

**Explain to students:**

- There are **two separate packages** at play:
  - `google.adk` — Google's Agent Development Kit. Provides `LlmAgent`, `to_a2a`, and the runtime.
  - `a2a.types` — The A2A protocol's type definitions (`AgentCard`, `AgentSkill`, `AgentCapabilities`). These are the standard protocol types, not Google-specific.
- `shared.callbacks` — Reusable logging callbacks from the shared infrastructure. This agent uses only the tool-level logging callbacks, not the model-level ones or guardrails. This is intentional: the weather agent has no dangerous operations to guard against.
- `shared.config` — The centralized settings singleton. The agent reads `settings.WEATHER_AGENT_URL` and `settings.GEMINI_MODEL` from here.
- `load_dotenv()` is called at the module level (line 28) to ensure environment variables are populated before `settings` is accessed.

**Teaching moment**: Notice the clean separation — protocol types come from the `a2a` package, Google ADK types come from `google.adk`, and project-specific code comes from `shared.*`. This three-layer import structure appears in every agent.

---

### 2. AgentSkill Definitions (lines 30–48)

```python
_weather_skill = AgentSkill(
    id="weather_lookup",
    name="Weather Lookup",
    description="Returns current weather conditions for a given city.",
    tags=["weather", "real-time"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

_forecast_skill = AgentSkill(
    id="weather_forecast",
    name="Weather Forecast",
    description="Returns a 5-day weather forecast for a given city.",
    tags=["weather", "forecast"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)
```

**Explain to students:**

- **Skills are advertisements, not implementations.** An `AgentSkill` declares what the agent can do; it does not wire to the actual tool function. The orchestrator reads skills from the AgentCard to decide which agent to route a request to.
- **`id`** must be unique within the agent. The orchestrator may use this for routing.
- **`tags`** enable discovery. If an orchestrator is looking for agents that handle `"weather"`, it can filter by tag.
- **`input_modes` / `output_modes`**: MIME types. Both are `"text/plain"` here, meaning the agent accepts and returns plain text. Other agents might support `"application/json"` or multimodal inputs.
- **Two skills, two tools**: This agent advertises two distinct capabilities. Each maps conceptually to one tool (`get_weather` and `get_forecast`), though the mapping is not enforced at the protocol level — the LLM decides which tool to invoke based on the user's request.

**Common confusion**: Students often conflate skills with tools. Emphasize that skills live at the **protocol layer** (what the outside world sees) while tools live at the **agent layer** (what the LLM can call). The LLM never sees `AgentSkill` objects; the orchestrator never sees `get_weather` function signatures.

---

### 3. AgentCard (lines 50–61)

```python
_AGENT_CARD = AgentCard(
    name="weather_agent",
    description="Retrieves real-time weather data and forecasts via OpenWeatherMap.",
    url=settings.WEATHER_AGENT_URL,       # F20 — resolved from env at startup
    version="1.0.0",
    skills=[_weather_skill, _forecast_skill],
    capabilities=AgentCapabilities(streaming=True),  # F3
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    # F8 — No authentication (securitySchemes is empty/omitted)
)
```

**Explain to students:**

- **The AgentCard is the A2A protocol's equivalent of an OpenAPI spec.** It tells other agents and clients everything they need to know before sending a request: what the agent does, where it lives, what it can handle, and what auth it requires.
- **`url`** comes from `settings.WEATHER_AGENT_URL`, which defaults to `http://localhost:8001` in local dev but is overridden by the environment in production (Cloud Run URL). This is feature F20 in action.
- **`capabilities=AgentCapabilities(streaming=True)`** — This advertises that the agent supports SSE streaming (feature F3). Clients can choose between `message/send` (synchronous, wait for full response) and `message/stream` (SSE, receive tokens as they are generated).
- **No `securitySchemes`** — This is feature F8. The agent is completely open, no authentication required. Compare this with the code agent (API key auth, F13) and research agent (JWT auth, F14).
- **`version="1.0.0"`** — Semantic versioning. Clients can use this to detect breaking changes.

**Teaching moment — where is the AgentCard served?** The `to_a2a()` wrapper automatically serves it at `/.well-known/agent.json`. This is the A2A protocol's standard discovery endpoint. When the orchestrator does `RemoteA2aAgent(agent_card_url="http://localhost:8001/.well-known/agent.json")`, it fetches this card.

---

### 4. System Instruction (lines 63–70)

```python
_SYSTEM_INSTRUCTION = """
You are a weather assistant. When a user asks about the weather in a city,
call the get_weather tool to retrieve current conditions.
For multi-day forecasts, call the get_forecast tool.
Always include temperature (C and F), conditions, humidity, and wind speed.
"""
```

**Explain to students:**

- The system instruction tells Gemini **how to behave** and **when to use each tool**. It is not part of the A2A protocol — it is purely an ADK/LLM concept.
- Note the output formatting requirement: "Always include temperature (C and F), conditions, humidity, and wind speed." This ensures consistent, structured responses regardless of how the user phrases their question.
- The instruction explicitly names both tools and describes when to use each. Without this guidance, the LLM might try to answer weather questions from its training data instead of calling the tools.

**Teaching moment**: System instructions are the primary way to control LLM behavior. A poorly written instruction leads to unreliable tool usage. A well-written one (like this) makes the agent predictable and testable.

---

### 5. LlmAgent Definition (lines 72–80)

```python
root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="weather_agent",
    description="Retrieves real-time weather data and forecasts.",
    instruction=_SYSTEM_INSTRUCTION,
    tools=[get_weather, get_forecast],
    before_tool_callback=logging_callback_before_tool,
    after_tool_callback=logging_callback_after_tool,
)
```

**Explain to students:**

- **`root_agent`** — The variable name matters. When using `adk api_server`, ADK discovers the agent by looking for a variable named `root_agent` in the module. This is a convention, not just a preference.
- **`model=settings.GEMINI_MODEL`** — Defaults to `gemini-2.0-flash`. All agents use the same model from the centralized config. Swap once in `.env`, every agent updates.
- **`tools=[get_weather, get_forecast]`** — These are plain Python `async def` functions. ADK inspects their type annotations and docstrings to auto-generate JSON schemas for function calling (feature F12). No manual schema definitions needed.
- **Callbacks** — Only tool-level logging callbacks are wired in. This agent does not use model callbacks (no need for token tracking in a simple weather agent) or guardrails (no dangerous operations). Compare with `code_agent/agent.py`, which adds `guardrail_callback_before_tool`.
- **No `before_model_callback` or `after_model_callback`** — This is a deliberate simplification. The weather agent is meant to be the easiest agent to understand. More complex agents add more callbacks.

**Teaching moment**: Ask students: "What would happen if we also wired in `cache_callback_before_tool` here?" Answer: Repeated weather queries for the same city would return cached results without calling the OpenWeatherMap API. Good for reducing API costs, bad for getting fresh weather data. This illustrates the trade-offs in callback composition.

---

### 6. FastAPI A2A Application (lines 82–88)

```python
app = to_a2a(root_agent, port=8001, agent_card=_AGENT_CARD)
```

**Explain to students:**

- **`to_a2a()`** is the magic function that bridges ADK and the A2A protocol. It takes an ADK agent and returns a fully configured FastAPI application that speaks the A2A protocol.
- **What `to_a2a()` sets up under the hood:**
  - `GET /.well-known/agent.json` — Serves the AgentCard for discovery (F1)
  - `POST /` — Handles JSON-RPC requests including:
    - `message/send` — Synchronous request/response (F2)
    - `message/stream` — SSE streaming (F3)
    - `tasks/*` — Task lifecycle management
- **`port=8001`** — Each agent runs on a different port. Weather is 8001, research is 8002, code is 8003, and so on.
- **`agent_card=_AGENT_CARD`** — Overrides the auto-generated card with our custom one. Without this, `to_a2a()` would generate a basic card from the LlmAgent's name and description, but we want explicit control over skills and capabilities.
- **`app`** — This variable is used by `uvicorn` directly: `uvicorn weather_agent.agent:app --port 8001`. It is also used by the Dockerfile for Cloud Run deployment (F20).

**Teaching moment**: The `to_a2a()` function is the key insight of this project. It shows that the A2A protocol is not something you implement from scratch — you wrap your existing agent with a one-line call and get a standards-compliant server. This is what makes A2A practical for real-world adoption.

---

## Design Patterns to Highlight

1. **Declarative Agent Definition**: The entire agent is defined declaratively — skills, card, instruction, tools, callbacks. There is no imperative logic in this file, no request handling, no HTTP routing. The framework handles all of that.

2. **Separation of Protocol and Logic**: The AgentCard (protocol layer) and the LlmAgent (logic layer) are defined separately and only joined at the `to_a2a()` call. You can change the card without touching the agent, or change the agent without touching the card.

3. **Convention over Configuration**: The `root_agent` variable name, the `/.well-known/agent.json` path, the JSON-RPC method names — all are conventions from ADK and the A2A spec. Students don't need to configure these; they just need to follow the conventions.

4. **Composition over Inheritance**: The agent is assembled from composable pieces — tools, callbacks, instruction, card — rather than subclassing a base agent. This makes it easy to mix and match behaviors.

5. **Configuration Externalization**: The URL and model are read from `settings`, not hardcoded. The agent works identically in local dev and Cloud Run without code changes.

---

## Common Student Questions

1. **"What is the difference between `description` in `AgentCard` and `description` in `LlmAgent`?"** The `AgentCard.description` is for external consumers (other agents, orchestrators, humans browsing the card). The `LlmAgent.description` is for the ADK runtime and is sometimes included in prompts to sub-agents. They can be different, but keeping them aligned avoids confusion.

2. **"Why does `to_a2a()` need both a `port` and the card has a `url`?"** The `port` tells uvicorn which port to bind to. The `url` in the card is the externally reachable address (which might be a Cloud Run URL, a load balancer, etc.). In local dev they align (`localhost:8001`), but in production they diverge.

3. **"Can I add more skills without adding more tools?"** Yes. Skills are advertisements. You could have one tool that handles multiple skills, or multiple tools behind one skill. The LLM's system instruction is what bridges the gap.

4. **"What if I want authentication on this agent?"** Add a `securitySchemes` field to the `AgentCard` and add middleware to the FastAPI app. See `code_agent/agent.py` for API key auth (F13) or `research_agent/agent.py` for JWT auth (F14).

5. **"Why `streaming=True` in capabilities? Doesn't ADK handle that automatically?"** ADK can stream, but the AgentCard must advertise it. If `streaming=False` (or omitted), clients should not attempt `message/stream` requests. The card is a contract.

---

## Related Files

- `weather_agent/tools.py` — The `get_weather` and `get_forecast` functions registered as tools
- `weather_agent/__init__.py` — Package docstring listing the features demonstrated
- `shared/config.py` — Provides `settings.WEATHER_AGENT_URL` and `settings.GEMINI_MODEL`
- `shared/callbacks.py` — Provides `logging_callback_before_tool` and `logging_callback_after_tool`
- `orchestrator_agent/agent.py` — The orchestrator that discovers and calls this agent via its AgentCard
- `tests/test_weather_agent.py` — Unit tests for the weather agent
- `Dockerfile` — Cloud Run deployment configuration (F20)
