# Agent-to-Agent (A2A) Protocol Demo — Technical Specification

## Overview

This project is a **comprehensive demonstration of all features in the Agent2Agent (A2A) Protocol**, built using **Google Agent Development Kit (ADK)** and deployed on **Google Cloud Platform (GCP) Vertex AI Agent Engine**.

The demo constructs a multi-agent ecosystem where specialized AI agents discover each other via Agent Cards, communicate over A2A, collaborate on tasks, stream results, push async notifications, and authenticate securely — showcasing every feature of the A2A specification (v0.3) in one runnable codebase.

### What the Demo Covers

| Module | Description |
|---|---|
| `orchestrator_agent` | Root LLM agent that routes tasks to remote specialist agents |
| `weather_agent` | Remote A2A agent exposing weather lookup capability |
| `research_agent` | Remote A2A agent with Google Search grounding |
| `code_agent` | Remote A2A agent performing sandboxed code execution |
| `data_agent` | Remote A2A agent processing structured data / files (Artifacts) |
| `async_agent` | Long-running remote A2A agent demonstrating push notifications |
| `pipeline_agent` | SequentialAgent coordinating multi-step workflows |
| `parallel_agent` | ParallelAgent running concurrent sub-agents |
| `loop_agent` | LoopAgent with exit-condition polling |
| `a2a_client` | Standalone A2A client consuming agents without ADK |

---

## Runtime & Language

| Component | Version |
|---|---|
| **Python** | 3.11+ (minimum 3.10; 3.11 recommended for GCP Vertex AI Agent Engine) |
| **Operating System** | Linux / macOS / Windows (Linux preferred for GCP) |
| **Package Manager** | pip 24+ |
| **Shell** | bash / zsh |

Python version check:
```bash
python --version   # must show 3.11.x or newer
```

---

## Tech Stack & Dependencies

### Core Framework

```
google-adk[a2a,eval,community,otel-gcp]==1.25.1
```

This single meta-package brings in:
- `google-genai` — Gemini model access (AI Studio + Vertex AI)
- `a2a-sdk` / `a2a` — the official A2A Python SDK
- Built-in evaluation tooling
- Community tools (web search helpers, etc.)
- OpenTelemetry GCP integration for observability

### Google Cloud / Vertex AI

```
google-cloud-aiplatform[agent_engines,adk]==1.112.0
google-cloud-storage==2.18.2
google-auth==2.38.0
google-auth-httplib2==0.2.0
```

### A2A SDK (standalone, already bundled by ADK a2a extra)

```
a2a-sdk==0.3.0
```

### Web Server (for local A2A server hosting)

```
uvicorn[standard]==0.34.0
fastapi==0.115.12
```

### Async & Networking

```
httpx==0.28.1
anyio==4.9.0
```

### gRPC Support (A2A v0.3 gRPC binding)

```
grpcio==1.71.0
grpcio-tools==1.71.0
protobuf==5.29.4
```

### Utilities

```
python-dotenv==1.0.1
pydantic==2.11.1
rich==13.9.4
typer==0.15.2
```

### Development / Testing

```
pytest==8.3.5
pytest-asyncio==0.25.3
pytest-httpx==0.35.0
```

### Full `requirements.txt`

```
# === Core ADK + A2A ===
google-adk[a2a,eval,community,otel-gcp]==1.25.1

# === GCP / Vertex AI ===
google-cloud-aiplatform[agent_engines,adk]==1.112.0
google-cloud-storage==2.18.2
google-auth==2.38.0
google-auth-httplib2==0.2.0

# === A2A SDK (explicit pin) ===
a2a-sdk==0.3.0

# === Web server ===
uvicorn[standard]==0.34.0
fastapi==0.115.12

# === Async & HTTP ===
httpx==0.28.1
anyio==4.9.0

# === gRPC (A2A v0.3 gRPC binding) ===
grpcio==1.71.0
grpcio-tools==1.71.0
protobuf==5.29.4

# === Utilities ===
python-dotenv==1.0.1
pydantic==2.11.1
rich==13.9.4
typer==0.15.2

# === Dev/Test ===
pytest==8.3.5
pytest-asyncio==0.25.3
pytest-httpx==0.35.0
```

### Install Commands

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# Install all dependencies
pip install -r requirements.txt

# Verify ADK CLI
adk --version
```

---

## Features List

### F1 — Agent Card (Discovery & Capability Advertisement)

**What:** Every A2A-exposed agent publishes a JSON "Agent Card" at `/.well-known/agent.json`, advertising its identity, skills, supported communication modes (sync/stream/push), and authentication requirements.

**Why it matters:** Agent Cards are the backbone of dynamic agent discovery — a client agent fetches the card before interaction to understand what the agent can do and how to authenticate with it.

**Implementation:**
- Use `to_a2a(agent, port=PORT)` which auto-generates the Agent Card from ADK agent metadata.
- Optionally supply a custom `AgentCard` object specifying `skills`, `capabilities`, `version`, `defaultInputModes`, `defaultOutputModes`.
- Demonstrate `capabilities.streaming=True` and `capabilities.pushNotifications=True`.

```python
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from a2a.types import AgentCard, AgentCapabilities, AgentSkill

skill = AgentSkill(
    id="weather_lookup",
    name="Weather Lookup",
    description="Returns current weather for a given city",
    inputModes=["text/plain"],
    outputModes=["text/plain"],
)
card = AgentCard(
    name="weather_agent",
    description="Retrieves real-time weather data",
    url="http://localhost:8001",
    version="1.0.0",
    skills=[skill],
    capabilities=AgentCapabilities(streaming=True, pushNotifications=True),
)
app = to_a2a(root_agent, port=8001, agent_card=card)
```

---

### F2 — Synchronous Request/Response (Send Message)

**What:** The most basic A2A interaction — a client sends a message to a remote agent and waits for an immediate response.

**Why:** Demonstrates the core JSON-RPC 2.0 `message/send` method and the `Task` + `Message` + `Artifact` data model.

**Key A2A objects:**
- `Message` — a single conversation turn (role: user/agent, parts: text/file/data)
- `Task` — stateful work unit returned when processing is needed
- `Artifact` — output artifact generated by the agent (file, data, document)

**Implementation:**
- Orchestrator agent delegates to a `RemoteA2aAgent` sub-agent.
- ADK handles all JSON-RPC framing transparently.

---

### F3 — Streaming via Server-Sent Events (SSE)

**What:** Real-time incremental result delivery using SSE (`message/stream` method). The server emits `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent` objects as work progresses.

**Why:** Necessary for long-running tasks (e.g., research synthesis, code generation) where users need live progress feedback rather than waiting for completion.

**Task stream sequence:**
```
Task(status=working) → TaskArtifactUpdateEvent(chunk1) → TaskArtifactUpdateEvent(chunk2)
  → TaskStatusUpdateEvent(completed)
```

**Implementation:**
- Agent server sets `capabilities.streaming=True` in its Agent Card.
- Server uses `on_message_stream()` handler in `DefaultA2ARequestHandler`.
- Client uses `RemoteA2aAgent` with streaming; ADK handles SSE subscription.

---

### F4 — Asynchronous Push Notifications (Webhooks)

**What:** For long-running tasks (minutes to hours), the client registers a webhook URL. The server POSTs `TaskStatusUpdateEvent` or `TaskArtifactUpdateEvent` to the webhook when the task state changes.

**Why:** Enables disconnected workflows — the client doesn't need to hold an HTTP connection open. Critical for enterprise batch processing scenarios.

**Agent Card declaration:**
```json
{
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  }
}
```

**Implementation:**
- `async_agent` accepts tasks that sleep for 10+ seconds (simulating long work).
- Client registers a webhook via `tasks/pushNotificationConfig/set`.
- A local FastAPI webhook server receives and logs delivery events.
- Demonstrates retry semantics and authentication of webhook delivery.

---

### F5 — Task Lifecycle Management

**What:** Full demonstration of the A2A Task state machine and management operations.

**Task states:**
```
submitted → working → input-required → working → completed
                                               → failed
                                               → canceled
                                               → rejected
```

**A2A Task methods demonstrated:**
| Method | Description |
|---|---|
| `message/send` | Start a new task or continue an existing one |
| `message/stream` | Start task with SSE streaming |
| `tasks/get` | Poll task status by ID |
| `tasks/list` | List tasks with filtering and cursor-based pagination |
| `tasks/cancel` | Cancel an in-progress task |
| `tasks/pushNotificationConfig/set` | Register webhook for task updates |
| `tasks/pushNotificationConfig/get` | Retrieve current webhook config |

**Implementation:**
- `loop_agent` demonstrates `input-required` state where agent pauses and asks the user for more data mid-task.
- `async_agent` demonstrates cancellation of a running task.

---

### F6 — Multi-Turn Conversation / Input Required

**What:** Agents can pause mid-task (status `input-required`) and request additional information from the calling agent or user. The conversation context is preserved across turns.

**Why:** Real agents often need clarification — e.g., "Which city?" or "Which format do you want?" — before completing work.

**Implementation:**
- `research_agent` pauses when the query is ambiguous, asking for clarification.
- The orchestrator receives the `input-required` status and sends a follow-up message with the same `taskId` to continue.

---

### F7 — Extended Agent Cards (Authenticated Capability Disclosure)

**What:** Some capabilities are only disclosed after authentication. The `agents/authenticatedExtendedCard` method returns an enriched Agent Card for authenticated clients, revealing additional skills or higher-privilege operations.

**Why:** Enables tiered access — public users see basic capabilities; authenticated enterprise clients see premium skills.

**Implementation:**
- Demonstrate `agents/authenticatedExtendedCard` call with Bearer token.
- Show different skill sets in public vs. authenticated card.

---

### F8 — Authentication Schemes

**What:** A2A supports OpenAPI-aligned authentication schemes. Agent Cards declare `securitySchemes` (API Key, OAuth 2.0, mTLS, OpenID Connect).

**Why:** Production agents must be secured. The demo shows all major schemes.

**Schemes demonstrated:**
| Scheme | Demo Agent |
|---|---|
| No auth (open) | `weather_agent` (local dev) |
| API Key header | `code_agent` (X-API-Key) |
| Bearer (JWT) | `research_agent` (simulated OAuth) |
| OAuth 2.0 client credentials | `data_agent` (GCP Service Account) |

**Implementation:**
- Use GCP Service Account JSON key as OAuth credential for Vertex AI-deployed agents.
- Demonstrate how ADK `RemoteA2aAgent` injects auth headers automatically from environment.

---

### F9 — Agent-to-Agent Routing (Orchestrator Pattern)

**What:** A root LLM agent (orchestrator) discovers and delegates to multiple specialist remote A2A agents based on the task at hand.

**Why:** This is the core value of A2A — decoupled, polyglot, independently deployable agents cooperating to solve complex tasks.

**Implementation using ADK:**
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH

weather_remote = RemoteA2aAgent(
    name="weather_agent",
    description="Handles weather queries for any city",
    agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}",
)

research_remote = RemoteA2aAgent(
    name="research_agent",
    description="Deep research using Google Search grounding",
    agent_card=f"http://localhost:8002{AGENT_CARD_WELL_KNOWN_PATH}",
)

orchestrator = LlmAgent(
    model="gemini-2.0-flash",
    name="orchestrator",
    instruction="Route user requests to the appropriate specialist agent.",
    sub_agents=[weather_remote, research_remote],
)
```

---

### F10 — Workflow Agents (Sequential, Parallel, Loop)

**What:** ADK workflow agents provide deterministic orchestration patterns over sub-agents.

| Agent Type | Pattern | Use Case |
|---|---|---|
| `SequentialAgent` | Assembly-line | Multi-step pipeline (research → summarize → format) |
| `ParallelAgent` | Fan-out/fan-in | Concurrent independent subtasks |
| `LoopAgent` | While-loop | Retry/polling until condition met |

**Implementation:**
- `pipeline_agent`: SequentialAgent with 3 stages (fetch → analyze → report).
- `parallel_agent`: Fans out weather queries for 5 cities simultaneously.
- `loop_agent`: Polls `async_agent` task status until completion (max 10 iterations).

---

### F11 — ADK Agent Types (LLM, Custom, Workflow)

**What:** Demonstrate all three core ADK agent classes.

**LlmAgent:**
- Backed by Gemini 2.0 Flash or Pro via Vertex AI.
- Uses function calling, tool use, system instructions.
- Dynamically decides which sub-agents/tools to invoke.

**Custom BaseAgent:**
- Extend `BaseAgent` directly for deterministic non-LLM logic.
- Example: `DataValidationAgent` that validates CSV format without LLM.

**Workflow Agents:**
- See F10 above.

---

### F12 — Tools: Function Tools, Built-in Tools, MCP Tools, OpenAPI Tools

**What:** Comprehensive demonstration of all ADK tool types that agents can use.

**Function Tools (custom Python):**
```python
def get_weather(city: str) -> dict:
    """Return current weather for a city."""
    ...  # call external weather API

agent = LlmAgent(tools=[get_weather], ...)
```

**Built-in Tools (Gemini-native):**
- `google_search` — real-time Google Search grounding
- `code_execution` — sandboxed Python code execution by Gemini

**MCP Tools (Model Context Protocol):**
```python
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
mcp_tools = McpToolset(connection_params=StdioServerParameters(
    command="npx",
    args=["@modelcontextprotocol/server-filesystem", "/tmp"],
))
```

**OpenAPI Tools:**
```python
from google.adk.tools.openapi_tool.openapi_toolset import OpenAPIToolset
openapi_tools = OpenAPIToolset(spec_file="weather_api.yaml")
```

---

### F13 — Session Management & State

**What:** ADK's session system maintains conversational context and agent state across turns.

**Key concepts:**
- `Session` — container for conversation history and state dict.
- `State` — key-value scratchpad persisted within a session.
- `InMemorySessionService` — local dev (no persistence).
- `VertexAiSessionService` — cloud-backed session storage.

**Implementation:**
- Show state passing between sequential pipeline stages.
- Use `context.state["result_key"]` to share data between tools.
- Demonstrate `temp:` prefixed keys for intra-invocation data.

---

### F14 — Memory Systems

**What:** Agents can recall information from past sessions using memory services.

**Memory types:**
| Type | Class | Description |
|---|---|---|
| In-process | `InMemoryMemoryService` | Ephemeral, dev-only |
| Vertex AI | `VertexAiRagMemoryService` | Persistent, RAG-backed |

**Implementation:**
- `research_agent` stores key facts from each session.
- On subsequent queries, memory is retrieved and injected into context.

---

### F15 — Artifacts (File & Binary Handling)

**What:** Agents produce and consume `Artifact` objects — files, images, PDFs, audio — that live outside session state.

**Why:** Tool outputs like generated CSV files, PDFs, or images can't fit in session state; Artifacts solve this.

**Implementation:**
- `data_agent` generates a CSV file as an Artifact.
- Artifact is returned in the A2A response as a `Part` with `type=file`.
- Orchestrator downloads and displays the artifact.

---

### F16 — Callbacks (Observe, Customize, Control)

**What:** Hook into agent lifecycle events before/after model calls and tool calls.

**Callback types:**
| Callback | Triggered |
|---|---|
| `before_model_callback` | Before LLM invocation |
| `after_model_callback` | After LLM response |
| `before_tool_callback` | Before tool execution |
| `after_tool_callback` | After tool result |
| `before_agent_callback` | Before agent run |
| `after_agent_callback` | After agent completes |

**Implementation examples:**
- Logging callback: print every model call with token counts.
- Guardrail callback: block tool calls with dangerous arguments.
- Cache callback: return cached results for repeated tool calls.

---

### F17 — Safety & Guardrails

**What:** Control what agents can say and do via input/output screening.

**Implementation:**
- `before_tool_callback` that blocks `code_execution` tool if code contains `os.system` or `subprocess`.
- `before_model_callback` that injects a safety system prompt.
- ADK Plugins for modular policy enforcement across all agents.

---

### F18 — Evaluation Framework

**What:** ADK's built-in eval harness measures agent quality.

**Implementation:**
- Create multi-turn eval datasets in JSON.
- Run `adk eval` CLI or `pytest` integration.
- Metrics: response correctness, tool call accuracy, trajectory adherence.

```bash
adk eval ./evals/orchestrator_eval.json --config ./eval_config.yaml
```

---

### F19 — Vertex AI Agent Engine Deployment

**What:** Deploy ADK agents to fully managed Vertex AI Agent Engine for production-scale hosting.

**Why:** Agent Engine handles scaling, session management, logging, and monitoring.

**Deployment command:**
```bash
adk deploy agent_engine \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  --display_name="a2a-demo-orchestrator" \
  ./orchestrator_agent/
```

**Programmatic deployment:**
```python
import vertexai
from vertexai import agent_engines

vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=f"gs://{BUCKET}")

remote_agent = agent_engines.create(
    agent_engine=AdkApp(agent=orchestrator, enable_tracing=True),
    requirements=["google-adk[a2a]==1.25.1", "cloudpickle==3.0"],
    display_name="a2a-demo",
)
```

---

### F20 — Cloud Run Deployment (A2A Server)

**What:** Deploy individual A2A agent servers to Cloud Run for stateless, auto-scaling microservices.

**Implementation:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
gcloud run deploy weather-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

---

### F21 — gRPC Transport (A2A v0.3)

**What:** A2A v0.3 adds gRPC as a transport binding alongside JSON-RPC and HTTP/REST. Uses Protocol Buffers for serialization, gRPC over HTTP/2 with TLS.

**Why:** gRPC provides better performance for high-throughput inter-service agent communication.

**Implementation:**
- Demonstrate standalone gRPC A2A server using `a2a-sdk`.
- Client sends `SendMessageRequest` using gRPC stub.
- Show `StreamMessageRequest` for gRPC streaming.

---

### F22 — Observability (OpenTelemetry + GCP Cloud Trace)

**What:** Instrument agents with distributed tracing using OpenTelemetry, exported to GCP Cloud Trace.

**Implementation:**
- Install `google-adk[otel-gcp]`.
- Set `GOOGLE_CLOUD_PROJECT` and enable the `enable_tracing=True` flag.
- View end-to-end traces across orchestrator → remote agents in Cloud Trace console.

---

### F23 — ADK Developer UI & CLI

**What:** ADK ships with a browser-based Dev UI for interactive testing and the `adk` CLI.

**CLI commands demonstrated:**
```bash
adk run ./orchestrator_agent/          # terminal chat
adk web ./orchestrator_agent/          # browser UI at localhost:8000
adk api_server --a2a ./weather_agent/  # expose as A2A server
adk eval ./evals/                      # run evaluation
adk deploy agent_engine ./             # deploy to Vertex AI
```

---

### F24 — Cross-Framework A2A Interoperability

**What:** Demonstrate that A2A is framework-agnostic — a raw Python A2A client (no ADK) can communicate with ADK-exposed agents, and vice versa.

**Implementation:**
- `a2a_client/` directory: pure `a2a-sdk` client without ADK.
- Send a message to the `weather_agent` A2A server using raw `a2a.client.A2AClient`.
- Show the A2A SDK `AgentCard` fetched from `/.well-known/agent.json`.

---

## Architecture Notes

```
┌─────────────────────────────────────────────────────────┐
│                    Demo Project Layout                  │
│                                                         │
│  orchestrator_agent/   ← LLM Agent (Vertex AI deployed) │
│    ├── agent.py        ← LlmAgent + RemoteA2aAgent refs │
│    └── tools.py        ← custom function tools          │
│                                                         │
│  weather_agent/        ← A2A Server (Cloud Run)         │
│    └── agent.py        ← LlmAgent + to_a2a()            │
│                                                         │
│  research_agent/       ← A2A Server (Cloud Run)         │
│    └── agent.py        ← Google Search grounding        │
│                                                         │
│  code_agent/           ← A2A Server (Cloud Run)         │
│    └── agent.py        ← Gemini code_execution tool     │
│                                                         │
│  data_agent/           ← A2A Server (Cloud Run)         │
│    └── agent.py        ← Artifact generation            │
│                                                         │
│  async_agent/          ← A2A Server (Cloud Run)         │
│    └── agent.py        ← Long-running + push notify     │
│                                                         │
│  pipeline_agent/       ← Local SequentialAgent          │
│  parallel_agent/       ← Local ParallelAgent            │
│  loop_agent/           ← Local LoopAgent                │
│                                                         │
│  a2a_client/           ← Standalone A2A SDK client      │
│  webhook_server/       ← FastAPI push notification sink │
│  evals/                ← ADK evaluation datasets        │
│  protos/               ← A2A gRPC .proto definitions    │
└─────────────────────────────────────────────────────────┘
```

### Communication Flow

```
User
  │  (natural language)
  ▼
orchestrator_agent  (Vertex AI Agent Engine)
  │
  ├──[A2A message/send]──► weather_agent     (Cloud Run :8001)
  ├──[A2A message/stream]─► research_agent   (Cloud Run :8002)
  ├──[A2A message/send]──► code_agent        (Cloud Run :8003)
  ├──[A2A message/send]──► data_agent        (Cloud Run :8004)
  └──[A2A async+webhook]──► async_agent     (Cloud Run :8005)
                                │
                                └──[HTTP POST]──► webhook_server (:9000)
```

### A2A Protocol Stack

```
Application Layer:  ADK Agents (LlmAgent, WorkflowAgent, CustomAgent)
                         │
A2A SDK Layer:      a2a-sdk (AgentCard, Task, Message, Artifact)
                         │
Transport Layer:    JSON-RPC 2.0 (HTTP/S)   ←── primary
                    Server-Sent Events       ←── streaming
                    gRPC + Protobuf          ←── v0.3 high-perf
                    Push Notifications       ←── async webhooks
```

### Data Model Relationships

```
AgentCard
  └── skills[]         (id, name, description, inputModes, outputModes)
  └── capabilities     (streaming, pushNotifications)
  └── securitySchemes  (apiKey, oauth2, oidc, mtls)

Task
  └── id               (unique task identifier)
  └── status           (submitted|working|input-required|completed|failed|canceled|rejected)
  └── history[]        (Message turns)
  └── artifacts[]      (Artifact outputs)
  └── metadata         (custom k/v)

Message
  └── role             (user | agent)
  └── parts[]
        └── TextPart   (string content)
        └── FilePart   (inline bytes or URL)
        └── DataPart   (JSON structured data)

Artifact
  └── artifactId
  └── parts[]          (same as Message parts)
```

---

## Setup Requirements

### Google Cloud Prerequisites

1. **GCP Project** with billing enabled.
2. **APIs to enable:**
   ```bash
   gcloud services enable \
     aiplatform.googleapis.com \
     run.googleapis.com \
     cloudbuild.googleapis.com \
     storage.googleapis.com \
     cloudresourcemanager.googleapis.com \
     secretmanager.googleapis.com
   ```
3. **GCS Bucket** for Agent Engine staging:
   ```bash
   gcloud storage buckets create gs://${PROJECT_ID}-a2a-demo \
     --location=us-central1
   ```

### Environment Variables

Create `.env` in the project root:

```dotenv
# ─── GCP / Vertex AI ───────────────────────────────────
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=1
VERTEXAI_STAGING_BUCKET=gs://your-project-id-a2a-demo

# ─── Gemini (AI Studio - for local dev without Vertex AI) ─
# GOOGLE_API_KEY=your-google-ai-studio-key
# Comment out GOOGLE_GENAI_USE_VERTEXAI when using AI Studio

# ─── A2A Agent URLs (local dev) ────────────────────────
WEATHER_AGENT_URL=http://localhost:8001
RESEARCH_AGENT_URL=http://localhost:8002
CODE_AGENT_URL=http://localhost:8003
DATA_AGENT_URL=http://localhost:8004
ASYNC_AGENT_URL=http://localhost:8005

# ─── A2A Agent URLs (Cloud Run production) ─────────────
# WEATHER_AGENT_URL=https://weather-agent-xxxx-uc.a.run.app
# RESEARCH_AGENT_URL=https://research-agent-xxxx-uc.a.run.app

# ─── Webhook server ────────────────────────────────────
WEBHOOK_SERVER_URL=http://localhost:9000
WEBHOOK_AUTH_TOKEN=demo-webhook-secret-token

# ─── API Keys for demo auth schemes ───────────────────
CODE_AGENT_API_KEY=demo-code-agent-key-12345

# ─── Observability ─────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.googleapis.com
```

### Authentication Setup

```bash
# Application Default Credentials (ADC) for local dev
gcloud auth application-default login

# Set default project
gcloud config set project $GOOGLE_CLOUD_PROJECT

# Verify ADC works
gcloud auth application-default print-access-token
```

### API Keys / External Services

| Service | Required For | How to Obtain |
|---|---|---|
| GCP Project | All Vertex AI features, Cloud Run | [GCP Console](https://console.cloud.google.com) |
| Google AI Studio Key | Local dev without Vertex AI | [aistudio.google.com](https://aistudio.google.com) |
| OpenWeatherMap API | `weather_agent` live data | [openweathermap.org/api](https://openweathermap.org/api) — free tier |
| GCP Service Account | OAuth 2.0 auth demo | Create via `gcloud iam service-accounts create` |

### Local Development Quick Start

```bash
# 1. Clone and setup
git clone <repo>
cd a2a-demo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# → edit .env with your values

# 2. Start all remote A2A agent servers (separate terminals or tmux)
adk api_server --a2a --port 8001 ./weather_agent/
adk api_server --a2a --port 8002 ./research_agent/
adk api_server --a2a --port 8003 ./code_agent/
adk api_server --a2a --port 8004 ./data_agent/
uvicorn async_agent.agent:app --port 8005  # manual uvicorn for push notify demo

# 3. Start webhook receiver
uvicorn webhook_server.main:app --port 9000

# 4. Run orchestrator in dev UI
adk web ./orchestrator_agent/
# → open http://localhost:8000
```

---

## References

### A2A Protocol
- [A2A Protocol Official Specification (latest)](https://a2a-protocol.org/latest/specification/)
- [A2A Protocol v0.3.0 Specification](https://a2a-protocol.org/v0.3.0/specification/)
- [A2A Streaming & Async Operations](https://a2a-protocol.org/latest/topics/streaming-and-async/)
- [A2A Agent Discovery](https://a2a-protocol.org/latest/topics/agent-discovery/)
- [GitHub: a2aproject/A2A](https://github.com/a2aproject/A2A)
- [Google Blog: Announcing the A2A Protocol](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [Google Cloud Blog: A2A Protocol Getting an Upgrade](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade)

### Google ADK
- [ADK Documentation Home](https://google.github.io/adk-docs/)
- [ADK Python Quickstart](https://google.github.io/adk-docs/get-started/python/)
- [ADK A2A Integration Overview](https://google.github.io/adk-docs/a2a/)
- [ADK A2A Intro](https://google.github.io/adk-docs/a2a/intro/)
- [ADK Quickstart: Exposing an Agent via A2A](https://google.github.io/adk-docs/a2a/quickstart-exposing/)
- [ADK Quickstart: Consuming a Remote A2A Agent](https://google.github.io/adk-docs/a2a/quickstart-consuming/)
- [ADK Multi-Agent Systems](https://google.github.io/adk-docs/agents/multi-agents/)
- [ADK Sequential Agents](https://google.github.io/adk-docs/agents/workflow-agents/sequential-agents/)
- [ADK Parallel Agents](https://google.github.io/adk-docs/agents/workflow-agents/parallel-agents/)
- [ADK Callbacks](https://google.github.io/adk-docs/callbacks/)
- [ADK Memory](https://google.github.io/adk-docs/sessions/memory/)
- [ADK Built-in Tools](https://google.github.io/adk-docs/tools/built-in-tools/)
- [ADK MCP Tools](https://google.github.io/adk-docs/tools-custom/mcp-tools/)
- [ADK Safety & Guardrails](https://google.github.io/adk-docs/safety/)
- [GitHub: google/adk-python](https://github.com/google/adk-python)
- [PyPI: google-adk](https://pypi.org/project/google-adk/)

### Vertex AI Agent Engine
- [Deploy ADK to Vertex AI Agent Engine](https://google.github.io/adk-docs/deploy/agent-engine/)
- [Vertex AI Agent Engine Overview](https://docs.cloud.google.com/agent-builder/agent-engine/overview)
- [Develop an ADK Agent on Vertex AI](https://docs.cloud.google.com/agent-builder/agent-engine/develop/adk)

### Codelabs & Examples
- [Codelab: Multi-Agent with ADK, A2A, MCP on Google Cloud (InstaVibe)](https://codelabs.developers.google.com/instavibe-adk-multi-agents/instructions)
- [Codelab: A2A Purchasing Concierge on Cloud Run + Agent Engine](https://codelabs.developers.google.com/intro-a2a-purchasing-concierge)
- [Codelab: Create Multi-Agent with ADK, Deploy to Agent Engine, A2A](https://codelabs.developers.google.com/codelabs/create-multi-agents-adk-a2a)
- [Google Cloud Blog: Build Multi-Agentic Systems with ADK](https://cloud.google.com/blog/products/ai-machine-learning/build-multi-agentic-systems-using-google-adk)
- [Google Developers Blog: ADK Multi-Agent Patterns](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/)
