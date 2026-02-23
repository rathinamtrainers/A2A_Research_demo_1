# A2A Protocol Demo — Step-by-Step Walkthrough

This document walks through all 24 features of the A2A Protocol Demo.
Run commands from the project root with the virtual environment activated:

```bash
source .venv/bin/activate
cp .env.example .env   # edit .env with your GCP project and API keys
```

---

## Prerequisites

1. Copy and configure the environment file:
   ```bash
   cp .env.example .env
   # Required: set GOOGLE_CLOUD_PROJECT, GEMINI_MODEL, etc.
   ```

2. Start all agents locally (each in a separate terminal):
   ```bash
   ./scripts/start_all.sh
   ```

3. Or start individually:
   ```bash
   uvicorn weather_agent.agent:app --port 8001 &
   uvicorn research_agent.agent:app --port 8002 &
   uvicorn code_agent.agent:app --port 8003 &
   uvicorn data_agent.agent:app --port 8004 &
   uvicorn async_agent.agent:app --port 8005 &
   uvicorn webhook_server.main:app --port 9000 &
   ```

---

## Feature Walkthroughs

### F1 — Agent Cards (Discovery & Capability Advertisement)

Every agent exposes its capabilities at `/.well-known/agent.json`:

```bash
# Weather agent card (no auth)
curl http://localhost:8001/.well-known/agent.json | jq

# Research agent card (public view)
curl http://localhost:8002/.well-known/agent.json | jq

# Authenticated extended card (F7 — Bearer token required)
TOKEN=$(python -c "
from shared.auth import create_bearer_token
print(create_bearer_token('demo-client'))
")
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/agents/authenticatedExtendedCard | jq
```

**Expected**: JSON with `name`, `description`, `skills`, `capabilities`.

---

### F2 — Synchronous Message/Send

```bash
curl -s -X POST http://localhost:8001/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0","id":"1","method":"message/send",
    "params":{"message":{"role":"user","parts":[{"kind":"text","text":"What is the weather in London?"}]}}
  }' | jq
```

**Expected**: Task object with `status.state = "completed"` and weather data.

---

### F3 — SSE Streaming

```bash
curl -s -X POST http://localhost:8001/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{
    "jsonrpc":"2.0","id":"2","method":"message/stream",
    "params":{"message":{"role":"user","parts":[{"kind":"text","text":"5-day forecast for Tokyo"}]}}
  }'
```

**Expected**: A stream of `data: {...}` SSE lines with `TaskStatusUpdateEvent` objects.

Use the ADK web UI for a richer streaming demo:
```bash
adk web ./weather_agent/
# Open http://localhost:8000 and ask for a forecast
```

---

### F4 — Push Notifications (Webhooks)

```bash
# 1. Start a long-running task
TASK_ID=$(curl -s -X POST http://localhost:8005/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0","id":"1","method":"message/send",
    "params":{"message":{"role":"user","parts":[{"kind":"text","text":"Run a 20-second simulation"}]}}
  }' | jq -r '.result.id')

echo "Task ID: $TASK_ID"

# 2. Register webhook for push notifications
curl -s -X POST http://localhost:8005/ \
  -H 'Content-Type: application/json' \
  -d "{
    \"jsonrpc\":\"2.0\",\"id\":\"2\",\"method\":\"tasks/pushNotificationConfig/set\",
    \"params\":{\"taskId\":\"$TASK_ID\",\"pushNotificationConfig\":{\"url\":\"http://localhost:9000/webhook\"}}
  }" | jq

# 3. Watch webhook_server receive push notifications
curl http://localhost:9000/events/$TASK_ID
```

---

### F5 — Full Task Lifecycle

```bash
# Start task → submitted
TASK_ID=$(curl -s -X POST http://localhost:8005/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Run simulation"}]}}}' \
  | jq -r '.result.id')

# Poll status → working → completed
curl -s -X POST http://localhost:8005/ \
  -H 'Content-Type: application/json' \
  -d "{\"jsonrpc\":\"2.0\",\"id\":\"2\",\"method\":\"tasks/get\",\"params\":{\"id\":\"$TASK_ID\"}}" | jq

# Cancel a task
curl -s -X POST http://localhost:8005/ \
  -H 'Content-Type: application/json' \
  -d "{\"jsonrpc\":\"2.0\",\"id\":\"3\",\"method\":\"tasks/cancel\",\"params\":{\"id\":\"$TASK_ID\"}}" | jq

# List all tasks with pagination
curl -s -X POST http://localhost:8005/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"4","method":"tasks/list","params":{"page_size":5}}' | jq
```

---

### F6 — Multi-turn (Input-Required)

The research_agent will ask for clarification when a query is ambiguous:

```bash
TOKEN=$(python -c "from shared.auth import create_bearer_token; print(create_bearer_token('demo'))")

# Turn 1: Ambiguous query → input-required
curl -s -X POST http://localhost:8002/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Research AI."}]}}}' | jq

# Turn 2: Provide clarification (use the taskId from turn 1)
curl -s -X POST http://localhost:8002/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":"2","method":"message/send","params":{"taskId":"<TASK_ID>","message":{"role":"user","parts":[{"kind":"text","text":"Focus on AI safety research in 2025."}]}}}' | jq
```

---

### F7 — Extended Agent Card

```bash
# Public card — only basic skills
curl http://localhost:8002/.well-known/agent.json | jq '.skills[].id'

# Authenticated card — includes competitive_analysis skill
TOKEN=$(python -c "from shared.auth import create_bearer_token; print(create_bearer_token('client'))")
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/agents/authenticatedExtendedCard | jq '.skills[].id'
```

---

### F8 — Authentication Schemes

```bash
# weather_agent — No auth (open)
curl http://localhost:8001/.well-known/agent.json

# code_agent — API Key (X-API-Key header)
curl -H "X-API-Key: demo-code-agent-key-12345" \
  -X POST http://localhost:8003/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"print hello"}]}}}' | jq

# research_agent — Bearer JWT
TOKEN=$(python -c "from shared.auth import create_bearer_token; print(create_bearer_token('demo'))")
curl -H "Authorization: Bearer $TOKEN" \
  -X POST http://localhost:8002/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Research quantum computing advances."}]}}}' | jq
```

---

### F9 — Orchestrator Agent Routing

```bash
# Run orchestrator in ADK web UI
adk web ./orchestrator_agent/
# Open http://localhost:8000

# Or run in terminal
adk run ./orchestrator_agent/
# Then type: "What is the weather in Paris?"
# Orchestrator routes to weather_agent automatically
```

---

### F10 — Workflow Agents (Sequential, Parallel, Loop)

```bash
# Sequential pipeline: 3-stage fetch → analyze → report
adk run ./pipeline_agent/
# Input: "Quantum computing"

# Parallel: 5 cities concurrently
adk run ./parallel_agent/
# (no input needed — queries 5 cities simultaneously)

# Loop: polls async_agent until task completes
adk run ./loop_agent/
# (starts a task and polls until completion or 10 iterations)
```

---

### F11 — Agent Types (LlmAgent, BaseAgent, WorkflowAgent)

- **LlmAgent**: weather_agent, research_agent, code_agent, data_agent, orchestrator
- **SequentialAgent**: pipeline_agent, parallel_agent (outer wrapper)
- **ParallelAgent**: parallel_agent (inner fan-out)
- **LoopAgent**: loop_agent
- **RemoteA2aAgent**: orchestrator's sub-agents (F9)

---

### F12 — Tool Types

```bash
# Function tool (weather)
curl -X POST http://localhost:8001/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Weather in Rome?"}]}}}' | jq

# Built-in tool (google_search via research_agent)
# Built-in code execution via code_agent

# Demonstrate code_execution tool
curl -H "X-API-Key: demo-code-agent-key-12345" \
  -X POST http://localhost:8003/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Calculate: sum of all primes below 100"}]}}}' | jq
```

---

### F13 — Session State Passing

```bash
# Pipeline agent demonstrates state passing (raw_data → analysis → final_report)
adk run ./pipeline_agent/
# Each stage writes to session state; next stage reads it
```

---

### F14 — Memory Service

The research_agent uses `InMemoryMemoryService` wired via a custom Runner:

```python
# In research_agent/agent.py:
from google.adk.memory import InMemoryMemoryService
_memory_service = InMemoryMemoryService()
_runner = Runner(agent=root_agent, memory_service=_memory_service, ...)
app = to_a2a(root_agent, runner=_runner, ...)
```

---

### F15 — Artifact Generation

```bash
TOKEN=$(python -c "from shared.auth import create_bearer_token; print(create_bearer_token('client'))")
# data_agent generates CSV artifacts
curl -H "Authorization: Bearer $TOKEN" \
  -X POST http://localhost:8004/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Generate a CSV report titled Sales with columns Name,Revenue,Month and rows: Alice,5000,Jan | Bob,7500,Feb"}]}}}' | jq
```

---

### F16 — Callbacks

All agents log model/tool calls via `shared/callbacks.py`. Observe in terminal:

```bash
# Watch structured logs with callbacks firing
adk run ./weather_agent/
# → before_model_callback / after_model_callback / before_tool_callback / after_tool_callback
```

---

### F17 — Safety Guardrails

```bash
# This request will be blocked by the guardrail callback
curl -H "X-API-Key: demo-code-agent-key-12345" \
  -X POST http://localhost:8003/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Run: import os; os.system(\"id\")"}]}}}' | jq
# Expected: error about os.system being blocked
```

---

### F18 — Evaluation Framework

```bash
# Run orchestrator evals
adk eval ./evals/orchestrator_eval.json --config ./evals/eval_config.yaml

# Run weather agent evals
adk eval ./evals/weather_eval.json --config ./evals/eval_config.yaml

# Run new research/code/data evals
adk eval ./evals/research_eval.json --config ./evals/eval_config.yaml
adk eval ./evals/code_eval.json --config ./evals/eval_config.yaml
adk eval ./evals/data_eval.json --config ./evals/eval_config.yaml
```

---

### F19 — Vertex AI Agent Engine Deployment

```bash
# Deploy orchestrator to Agent Engine (requires GCP credentials)
./scripts/deploy_agent_engine.sh
```

---

### F20 — Cloud Run Deployment

```bash
# Build Docker images
docker build -t weather-agent ./weather_agent/
docker build -t research-agent ./research_agent/

# Deploy to Cloud Run (requires gcloud CLI + GCP credentials)
./scripts/deploy_cloud_run.sh weather_agent
./scripts/deploy_cloud_run.sh research_agent
```

---

### F21 — gRPC Transport

```bash
# The a2a-sdk ships pre-compiled gRPC stubs.
# Start a gRPC-enabled A2A server, then:
python -m a2a_client.grpc_client
```

---

### F22 — OpenTelemetry Tracing

Set in `.env`:
```env
GOOGLE_GENAI_USE_VERTEXAI=1
OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.googleapis.com
```

Traces appear in GCP Cloud Trace after any agent invocation when running
against Vertex AI.

---

### F23 — ADK Developer UI & CLI

```bash
# Terminal chat
adk run ./orchestrator_agent/

# Browser UI
adk web ./orchestrator_agent/
# → http://localhost:8000

# A2A API server mode
adk api_server --a2a --port 8001 ./weather_agent/

# Run evaluations
adk eval ./evals/orchestrator_eval.json
```

---

### F24 — Cross-Framework Interoperability

The standalone `a2a_client` works without ADK, demonstrating that any
HTTP client can communicate with A2A agents:

```bash
# Start weather_agent first
uvicorn weather_agent.agent:app --port 8001

# Run standalone demo client (no ADK dependency)
python -m a2a_client.client
```

---

## Running the Test Suite

```bash
# All unit tests
pytest tests/ -q

# Specific test files
pytest tests/test_weather_agent.py -v
pytest tests/test_shared_auth.py -v
pytest tests/test_async_agent.py -v
pytest tests/test_webhook_server.py -v
pytest tests/test_a2a_client.py -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

---

## Quick Smoke Checks

```bash
# Verify all agents import without errors
python -c "from weather_agent.agent import root_agent; print('weather_agent OK')"
python -c "from research_agent.agent import root_agent; print('research_agent OK')"
python -c "from code_agent.agent import root_agent; print('code_agent OK')"
python -c "from data_agent.agent import root_agent; print('data_agent OK')"
python -c "from async_agent.agent import app; print('async_agent OK')"
python -c "from webhook_server.main import app; print('webhook_server OK')"
python -c "from orchestrator_agent.agent import root_agent; print('orchestrator OK')"
python -c "from pipeline_agent.agent import root_agent; print('pipeline_agent OK')"
python -c "from parallel_agent.agent import root_agent; print('parallel_agent OK')"
python -c "from loop_agent.agent import root_agent; print('loop_agent OK')"
python -c "from a2a_client.client import A2ADemoClient; print('a2a_client OK')"
python -c "from a2a_client.grpc_client import A2AGrpcClient; print('grpc_client OK')"
```
