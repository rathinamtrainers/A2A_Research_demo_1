# A2A Protocol Demo

A **comprehensive demonstration of all features in the Agent2Agent (A2A) Protocol**,
built using **Google Agent Development Kit (ADK) 1.25.1** and deployable to
**Google Cloud Platform (GCP) Vertex AI Agent Engine + Cloud Run**.

This project constructs a multi-agent ecosystem where specialist AI agents
discover each other via Agent Cards, communicate over A2A, collaborate on
tasks, stream results, push async notifications, and authenticate securely —
showcasing all 24 features of the A2A v0.3 specification in one runnable codebase.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Demo Project Layout                  │
│                                                         │
│  orchestrator_agent/   ← LLM Agent (Vertex AI deployed)│
│  weather_agent/        ← A2A Server (Cloud Run :8001)  │
│  research_agent/       ← A2A Server (Cloud Run :8002)  │
│  code_agent/           ← A2A Server (Cloud Run :8003)  │
│  data_agent/           ← A2A Server (Cloud Run :8004)  │
│  async_agent/          ← A2A Server (Cloud Run :8005)  │
│  pipeline_agent/       ← Local SequentialAgent         │
│  parallel_agent/       ← Local ParallelAgent           │
│  loop_agent/           ← Local LoopAgent               │
│  a2a_client/           ← Standalone A2A SDK client     │
│  webhook_server/       ← FastAPI push notification sink│
│  evals/                ← ADK evaluation datasets       │
│  protos/               ← A2A gRPC .proto definitions   │
│  scripts/              ← Dev/deployment shell scripts  │
│  shared/               ← Common config, auth, callbacks│
│  tests/                ← Full pytest test suite        │
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

---

## Features Demonstrated

| Feature | Description | Agent(s) |
|---|---|---|
| F1 — Agent Card | Custom AgentCard with skills, capabilities, security | All |
| F2 — Sync Request/Response | `message/send` JSON-RPC | All |
| F3 — SSE Streaming | `message/stream` Server-Sent Events | weather, research |
| F4 — Push Notifications | Webhook delivery, `tasks/pushNotificationConfig/*` | async |
| F5 — Task Lifecycle | Full state machine, `tasks/get`, `tasks/cancel` | async, loop |
| F6 — Multi-turn | `input-required` state, conversation continuation | research, loop |
| F7 — Extended Card | Authenticated capability disclosure | research |
| F8 — Auth Schemes | No-auth, API Key, Bearer JWT, OAuth 2.0 | All |
| F9 — A2A Routing | Orchestrator → specialist agents via `RemoteA2aAgent` | orchestrator |
| F10 — Workflow Agents | SequentialAgent, ParallelAgent, LoopAgent | pipeline, parallel, loop |
| F11 — Agent Types | LlmAgent, BaseAgent, WorkflowAgent | All |
| F12 — Tool Types | Function, Google Search, code_execution, MCP, OpenAPI | All |
| F13 — Session State | `context.state`, `InMemorySessionService` | pipeline |
| F14 — Memory | `InMemoryMemoryService`, `VertexAiRagMemoryService` | research |
| F15 — Artifacts | CSV/JSON file artifacts | data |
| F16 — Callbacks | Logging, before/after model and tool | All |
| F17 — Safety/Guardrails | Dangerous code pattern blocking | code |
| F18 — Evaluation | ADK eval datasets + `adk eval` CLI | evals/ |
| F19 — Agent Engine | Vertex AI Agent Engine deployment | orchestrator |
| F20 — Cloud Run | Dockerised microservice deployment | All remotes |
| F21 — gRPC Transport | A2A v0.3 Protobuf/gRPC binding | a2a_client/grpc |
| F22 — Observability | OpenTelemetry → GCP Cloud Trace | orchestrator |
| F23 — ADK Dev UI | `adk run`, `adk web`, `adk api_server` | All |
| F24 — Interoperability | Pure a2a-sdk client without ADK | a2a_client |

---

## Quick Start

### Prerequisites

- Python 3.11+
- GCP project with billing enabled (see `ENV_SETUP.md`)
- `gcloud` CLI authenticated

### Setup

```bash
# 1. Clone and enter project
git clone <repo> && cd a2a-demo

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Copy and configure environment
cp .env.example .env
# Edit .env with your GCP project, API keys, etc.

# 4. Make scripts executable
chmod +x scripts/*.sh
```

### Run All Agents Locally

```bash
# Start all remote agent servers (background):
./scripts/start_all.sh

# Start orchestrator in Dev UI:
adk web ./orchestrator_agent/
# → Open http://localhost:8000

# Stop all:
./scripts/stop_all.sh
```

### Run Tests

```bash
pytest tests/ -v
```

### Deploy to GCP

```bash
# Deploy all remote agents to Cloud Run:
./scripts/deploy_cloud_run.sh

# Deploy orchestrator to Vertex AI Agent Engine:
./scripts/deploy_agent_engine.sh
```

---

## Directory Reference

| Directory | Purpose |
|---|---|
| `shared/` | Config loader, auth helpers, reusable callbacks |
| `orchestrator_agent/` | Root LLM agent + tools + callbacks |
| `weather_agent/` | Weather lookup A2A server |
| `research_agent/` | Google Search research A2A server |
| `code_agent/` | Code execution A2A server |
| `data_agent/` | Data processing + Artifacts A2A server |
| `async_agent/` | Long-running tasks + push notifications |
| `pipeline_agent/` | 3-stage SequentialAgent pipeline |
| `parallel_agent/` | Concurrent city weather ParallelAgent |
| `loop_agent/` | Task polling LoopAgent |
| `a2a_client/` | Standalone HTTP + gRPC A2A client |
| `webhook_server/` | FastAPI push notification receiver |
| `evals/` | ADK evaluation datasets and config |
| `protos/` | gRPC Protobuf service definitions |
| `scripts/` | Start/stop/deploy shell scripts |
| `tests/` | pytest test suite |

---

## References

- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [Vertex AI Agent Engine](https://google.github.io/adk-docs/deploy/agent-engine/)
- [ENV_SETUP.md](./ENV_SETUP.md) — GCP setup and API key guide
- [PLAN.md](./PLAN.md) — Detailed implementation checklist
