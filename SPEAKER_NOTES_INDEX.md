# Speaker Notes — Master Navigation

> **How to use this document**: Read top to bottom. The order follows a
> request as it flows through the system — from the client that sends it,
> through the orchestrator that routes it, down to the specialist agent
> that handles it, and into the shared infrastructure that supports everything.
>
> **Total teaching time**: ~6.5 hours (all notes) or ~90 minutes (highlights
> from `SPEAKER_NOTES.md`)

---

## Architecture — Request Flow (Top to Bottom)

```
    ┌─────────────────────────────────────────────────────────┐
    │                      Clients                            │  Layer 1: Request enters here
    │              a2a_client (HTTP / gRPC)                   │
    │         "What is the weather in Paris?"                 │
    └────────────────────────┬────────────────────────────────┘
                             │  JSON-RPC over HTTP
                             ▼
    ┌─────────────────────────────────────────────────────────┐
    │                    Orchestrator                          │  Layer 2: Routes to specialist
    │                 orchestrator_agent                       │
    │          "This is a weather question → weather_agent"    │
    └────────────────────────┬────────────────────────────────┘
                             │  A2A protocol (RemoteA2aAgent)
                             ▼
    ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
    │ weather  ││ research ││   code   ││   data   ││  async   │  Layer 3: Does the actual work
    │  :8001   ││  :8002   ││  :8003   ││  :8004   ││  :8005   │
    └────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘
         │           │           │           │           │
         └───────────┴───────────┼───────────┴───────────┘
                                 ▼
    ┌─────────────────────────────────────────────────────────┐
    │                  Shared Library                          │  Layer 4: Foundation everything
    │            config / auth / callbacks                     │  depends on
    └─────────────────────────────────────────────────────────┘

    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │   Workflow   │    │   Webhook    │    │    Tests     │    Supporting systems
    │    Agents    │    │   Server     │    │              │    (side topics)
    └──────────────┘    └──────────────┘    └──────────────┘
```

### How a Request Flows Through the System

Let's trace what happens when a user asks **"What is the weather in Paris?"**

**1. Client sends a JSON-RPC request**

The client (`a2a_client/client.py`) doesn't know anything about agents,
Gemini, or ADK. It only knows the A2A protocol: fetch an Agent Card from
`/.well-known/agent.json`, then POST a JSON-RPC message to the agent's URL.
The payload is a standard `message/send` request with a text part. This is
the interoperability promise — any language, any framework, just HTTP.

**2. Orchestrator receives and routes**

The orchestrator (`orchestrator_agent/agent.py`) is an `LlmAgent` backed by
Gemini 2.0 Flash. It reads the user's message and its system instruction,
which lists five specialist agents with descriptions like *"Handles weather
queries for any city."* Gemini matches "weather in Paris" to `weather_agent`
and transfers control. There are no `if/else` routing rules — the LLM
decides.

Under the hood, `RemoteA2aAgent` fetches the weather agent's Agent Card to
discover its endpoint, then forwards the message over A2A (another JSON-RPC
POST). For agents that require auth (research, code, data), the orchestrator
attaches pre-configured httpx clients with the right headers.

**3. Specialist agent does the work**

The weather agent (`weather_agent/agent.py`) is another `LlmAgent`. It
receives the forwarded message, and Gemini decides to call the `get_weather`
tool with `city="Paris"`. The tool function hits the OpenWeatherMap API (or
returns mock data), and Gemini formats the result into a human-readable
response: *"Paris: 18.5°C, scattered clouds, humidity 65%."*

The response travels back: weather agent → orchestrator → client.

**4. Shared library supports everything**

None of this works without the shared foundation:
- `shared/config.py` — Every agent reads its URL, model name, and API keys
  from the same `Settings` dataclass. Change one `.env` variable, every agent
  updates.
- `shared/auth.py` — The research agent's JWT middleware, the code agent's
  API key check, the webhook server's HMAC verification — all implemented here.
- `shared/callbacks.py` — Before every LLM call, a logging callback prints
  the agent name and message count. Before every tool call, a guardrail
  callback checks for dangerous patterns. After every tool call, a cache
  callback stores the result.

### What Makes This an A2A Demo (Not Just a Multi-Agent App)

The key difference is the **protocol boundary** between agents. Each
specialist agent is a separate HTTP server with its own:

- **Agent Card** — a JSON document at `/.well-known/agent.json` that
  advertises capabilities, skills, and auth requirements
- **JSON-RPC endpoint** — accepts `message/send`, `message/stream`,
  `tasks/get`, and other standard A2A methods
- **Independent deployment** — can be written in any language, deployed
  anywhere, scaled independently

The orchestrator doesn't import the weather agent's code. It discovers it
over HTTP, authenticates using the scheme declared in the Agent Card, and
communicates using the A2A JSON-RPC protocol. Replace the weather agent
with a Java implementation and the orchestrator wouldn't notice.

This is what A2A enables: **agents built by different teams, in different
languages, on different infrastructure, that can discover and communicate
with each other through a standard protocol.**

### The Four Auth Patterns

Each agent demonstrates a different authentication scheme:

| Agent | Auth | How It Works |
|-------|------|-------------|
| weather | None | Open — anyone can call it |
| code | API Key | Client sends `X-API-Key` header; agent checks against `settings.CODE_AGENT_API_KEY` |
| research | Bearer JWT | Client sends HMAC-signed token; agent verifies signature with shared secret |
| data | OAuth 2.0 / Bearer | GCP service account token in production; demo Bearer token for local dev |
| async | None | Open — simulates long-running tasks |

The orchestrator handles this transparently — each `RemoteA2aAgent` is
configured with an `httpx.AsyncClient` that has the correct auth headers
pre-set.

### The Supporting Systems

**Workflow agents** (pipeline, parallel, loop) are not part of the main
request flow. They demonstrate ADK's local orchestration patterns —
composing multiple agents without A2A network calls:

| Pattern | What It Does | Real-World Use Case |
|---------|-------------|---------------------|
| Pipeline (`SequentialAgent`) | A → B → C, each reading the previous output | Multi-stage document processing |
| Parallel (`ParallelAgent`) | A + B + C at the same time | Querying multiple data sources concurrently |
| Loop (`LoopAgent`) | Repeat A → B until done | Polling for task completion, iterative refinement |

**Webhook server** receives push notifications from the async agent when
long-running tasks complete. It verifies HMAC signatures and stores events.

**Tests** use pytest fixtures from `tests/conftest.py` to mock Gemini
responses and test agents without real API calls.

---

## Layer 1 — Clients (where the request starts)

A user or external system sends a request. These clients prove that any
HTTP client can talk A2A — no SDK required.

| # | File | Speaker Notes | Time | What You'll Learn |
|---|------|---------------|------|-------------------|
| 1 | `a2a_client/client.py` | [`a2a_client/SPEAKER_NOTES_client_py.md`](a2a_client/SPEAKER_NOTES_client_py.md) | 20-25 min | Raw HTTP/JSON-RPC client — no ADK, just httpx |
| 2 | `a2a_client/grpc_client.py` | [`a2a_client/SPEAKER_NOTES_grpc_client_py.md`](a2a_client/SPEAKER_NOTES_grpc_client_py.md) | 20-25 min | gRPC/Protobuf as an alternative transport |

> Start here to understand **what a request looks like** before diving into
> what processes it. The HTTP client shows the exact JSON-RPC payload, the
> Agent Card discovery call, and SSE streaming — all in plain httpx.

---

## Layer 2 — Orchestrator (where the request gets routed)

The request hits the orchestrator. Gemini reads the user's message and the
descriptions of all 5 sub-agents, then decides which one to call.

| # | File | Speaker Notes | Time | What You'll Learn |
|---|------|---------------|------|-------------------|
| 3 | `orchestrator_agent/agent.py` | [`orchestrator_agent/SPEAKER_NOTES_agent_py.md`](orchestrator_agent/SPEAKER_NOTES_agent_py.md) | 15-20 min | `RemoteA2aAgent`, LLM-as-router, httpx auth clients, hub-and-spoke |
| 4 | `orchestrator_agent/tools.py` | [`orchestrator_agent/SPEAKER_NOTES_tools_py.md`](orchestrator_agent/SPEAKER_NOTES_tools_py.md) | 8-12 min | Agent introspection: `list_available_agents`, `get_agent_status` |
| 5 | `orchestrator_agent/callbacks.py` | [`orchestrator_agent/SPEAKER_NOTES_callbacks_py.md`](orchestrator_agent/SPEAKER_NOTES_callbacks_py.md) | 10-15 min | Safety prefix injection, URL redaction |

> Key concept: no hard-coded routing rules. The LLM reads sub-agent
> descriptions and decides. This is "LLM-as-router."

---

## Layer 3 — Specialist Agents (where the work happens)

The orchestrator forwards the request to one of these agents over A2A.
Each is a standalone microservice.

Start with weather (simplest), then progress to more complex agents.

### Weather Agent (simplest — the blueprint)

| # | File | Speaker Notes | Time | What You'll Learn |
|---|------|---------------|------|-------------------|
| 6 | `weather_agent/agent.py` | [`weather_agent/SPEAKER_NOTES_agent_py.md`](weather_agent/SPEAKER_NOTES_agent_py.md) | 15-20 min | AgentCard, LlmAgent, `to_a2a()` — the complete A2A pattern |
| 7 | `weather_agent/tools.py` | [`weather_agent/SPEAKER_NOTES_tools_py.md`](weather_agent/SPEAKER_NOTES_tools_py.md) | 15-20 min | Function tools, OpenWeatherMap API, mock fallback |

> Every other agent follows the same 4-step pattern: define skills →
> create AgentCard → build LlmAgent → wrap with `to_a2a()`. Learn this
> one and you have the blueprint for all the rest.

### Research Agent (most complex single agent)

| # | File | Speaker Notes | Time | What You'll Learn |
|---|------|---------------|------|-------------------|
| 8 | `research_agent/agent.py` | [`research_agent/SPEAKER_NOTES_agent_py.md`](research_agent/SPEAKER_NOTES_agent_py.md) | 25-35 min | Extended Agent Card, Bearer JWT, memory service, Google Search grounding, Starlette middleware |

> Adds 4 layers on top of the weather pattern: JWT auth middleware,
> extended card for authenticated clients, `InMemoryMemoryService` for
> cross-session recall, and `google_search` as a built-in tool.

### Code Agent (guardrails + code execution)

| # | File | Speaker Notes | Time | What You'll Learn |
|---|------|---------------|------|-------------------|
| 9 | `code_agent/agent.py` | [`code_agent/SPEAKER_NOTES_agent_py.md`](code_agent/SPEAKER_NOTES_agent_py.md) | 15-20 min | API key auth, `BuiltInCodeExecutor`, guardrail callbacks, safety patterns |

> Two layers of defense: Gemini's safety training refuses to generate
> dangerous code, and the guardrail callback blocks patterns like
> `os.system` and `subprocess` before execution.

### Data Agent (artifacts + OAuth)

| # | File | Speaker Notes | Time | What You'll Learn |
|---|------|---------------|------|-------------------|
| 10 | `data_agent/agent.py` | [`data_agent/SPEAKER_NOTES_agent_py.md`](data_agent/SPEAKER_NOTES_agent_py.md) | 15-20 min | OAuth 2.0 middleware, Artifact generation, multi-modal output |
| 11 | `data_agent/tools.py` | [`data_agent/SPEAKER_NOTES_tools_py.md`](data_agent/SPEAKER_NOTES_tools_py.md) | 12-15 min | CSV parsing, statistics, creating A2A Artifacts |

> Introduces **Artifacts** — structured file outputs (CSV, JSON) returned
> alongside the text response.

### Async Agent (hand-rolled A2A, no LLM)

| # | File | Speaker Notes | Time | What You'll Learn |
|---|------|---------------|------|-------------------|
| 12 | `async_agent/agent.py` | [`async_agent/SPEAKER_NOTES_agent_py.md`](async_agent/SPEAKER_NOTES_agent_py.md) | 35-45 min | Task lifecycle, push notifications, SSE streaming, task cancellation — all without ADK |

> The most unique agent. It does **not** use `LlmAgent` or `to_a2a()`.
> It implements A2A JSON-RPC by hand with raw FastAPI routes. This proves
> A2A is framework-agnostic.

---

## Layer 4 — Shared Foundation (what everything depends on)

Every agent imports from `shared/`. This is the bedrock the entire system
is built on.

| # | File | Speaker Notes | Time | What You'll Learn |
|---|------|---------------|------|-------------------|
| 13 | `shared/__init__.py` | [`shared/SPEAKER_NOTES___init___py.md`](shared/SPEAKER_NOTES___init___py.md) | 3-5 min | Package re-exports, import convenience |
| 14 | `shared/config.py` | [`shared/SPEAKER_NOTES_config_py.md`](shared/SPEAKER_NOTES_config_py.md) | 10-15 min | Settings dataclass, .env loading, fail-fast validation |
| 15 | `shared/auth.py` | [`shared/SPEAKER_NOTES_auth_py.md`](shared/SPEAKER_NOTES_auth_py.md) | 15-20 min | All 4 auth schemes: none, API key, Bearer JWT, HMAC webhook |
| 16 | `shared/callbacks.py` | [`shared/SPEAKER_NOTES_callbacks_py.md`](shared/SPEAKER_NOTES_callbacks_py.md) | 15-20 min | ADK callback hooks: logging, guardrails, caching |

> By the time you reach this layer, you've already seen these modules
> used in every agent above. Now you understand **why** they exist and
> **how** they work internally.

---

## Supporting Systems

### Workflow Agents (orchestration patterns)

These compose agents using ADK's workflow primitives. They are side topics
— not part of the main request flow, but important for understanding ADK's
orchestration capabilities.

| # | File | Speaker Notes | Time | Pattern | Execution |
|---|------|---------------|------|---------|-----------|
| 17 | `pipeline_agent/agent.py` | [`pipeline_agent/SPEAKER_NOTES_agent_py.md`](pipeline_agent/SPEAKER_NOTES_agent_py.md) | 15-20 min | `SequentialAgent` | A → B → C (assembly line) |
| 18 | `parallel_agent/agent.py` | [`parallel_agent/SPEAKER_NOTES_agent_py.md`](parallel_agent/SPEAKER_NOTES_agent_py.md) | 15-20 min | `ParallelAgent` | A + B + C (fan-out / fan-in) |
| 19 | `loop_agent/agent.py` | [`loop_agent/SPEAKER_NOTES_agent_py.md`](loop_agent/SPEAKER_NOTES_agent_py.md) | 15-20 min | `LoopAgent` | A → B → A → B (poll until done) |

### Webhook Server & Tests

| # | File | Speaker Notes | Time | What You'll Learn |
|---|------|---------------|------|-------------------|
| 20 | `webhook_server/main.py` | [`webhook_server/SPEAKER_NOTES_main_py.md`](webhook_server/SPEAKER_NOTES_main_py.md) | 15-20 min | Push notification receiver, HMAC verification, event storage |
| 21 | `tests/conftest.py` | [`tests/SPEAKER_NOTES_conftest_py.md`](tests/SPEAKER_NOTES_conftest_py.md) | 10-15 min | Pytest fixtures, mock patterns, test infrastructure |

---

## Comprehensive Reference

| # | File | Speaker Notes | Time |
|---|------|---------------|------|
| -- | *(entire project)* | [`SPEAKER_NOTES.md`](SPEAKER_NOTES.md) | 3-4 hrs |

> The root `SPEAKER_NOTES.md` is a single monolithic document covering
> all 24 A2A features, all agents, architecture, deployment, and a live
> demo script. Use it as a reference or for a complete deep-dive session.

---

## Suggested Teaching Paths

### Path A: Quick Overview (90 minutes)

Read the root [`SPEAKER_NOTES.md`](SPEAKER_NOTES.md) — it has a highlights
track built in.

### Path B: Top-Down Architecture (3 hours)

Follow this index top to bottom:
1. Client (#1) — see what a request looks like — 20 min
2. Orchestrator (#3) — see how it gets routed — 20 min
3. Weather agent (#6-7) — see how a specialist handles it — 30 min
4. One complex agent: research (#8) or async (#12) — 35 min
5. Shared foundation (#14-16) — now understand the internals — 40 min
6. One workflow pattern: pipeline (#17) — 20 min

### Path C: Feature-Focused (pick and choose)

| Feature | Notes to Read |
|---------|---------------|
| Agent Card & Discovery | #6 (weather agent) |
| Authentication | #15 (shared/auth) → #8 (research) → #9 (code) |
| Callbacks & Safety | #16 (shared/callbacks) → #9 (code) → #5 (orchestrator callbacks) |
| A2A Routing | #3 (orchestrator agent) |
| Streaming & Async | #12 (async agent) → #20 (webhook server) |
| Workflow Patterns | #17 (pipeline) → #18 (parallel) → #19 (loop) |
| Interoperability | #1 (HTTP client) → #2 (gRPC client) |
| Artifacts | #10 + #11 (data agent) |
