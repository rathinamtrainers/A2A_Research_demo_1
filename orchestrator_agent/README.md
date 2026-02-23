# orchestrator_agent/

Root LLM agent that receives user requests and routes them to specialist
remote A2A agents.

## Features Demonstrated

| Feature | Description |
|---|---|
| F9 — A2A Routing | Routes to weather, research, code, data, async agents via `RemoteA2aAgent` |
| F11 — LlmAgent | Backed by Gemini 2.0 Flash on Vertex AI |
| F13 — Session State | Stateful conversation context across turns |
| F16 — Callbacks | Logging before/after model; safety guardrails |
| F19 — Agent Engine | Deployment target for Vertex AI Agent Engine |
| F22 — Observability | OpenTelemetry tracing via `enable_tracing=True` |

## Files

| File | Purpose |
|---|---|
| `agent.py` | `root_agent` definition — LlmAgent with 5 RemoteA2aAgent sub-agents |
| `tools.py` | `list_available_agents`, `get_agent_status` function tools |
| `callbacks.py` | Before/after model callbacks: logging + URL redaction |
| `Dockerfile` | Container definition for Cloud Run / Agent Engine |

## Running Locally

```bash
# Terminal chat
adk run ./orchestrator_agent/

# Browser Dev UI at http://localhost:8000
adk web ./orchestrator_agent/

# Prerequisites: all remote agents must be running
#   weather_agent  → http://localhost:8001
#   research_agent → http://localhost:8002
#   code_agent     → http://localhost:8003
#   data_agent     → http://localhost:8004
#   async_agent    → http://localhost:8005
```

## Deployment

```bash
adk deploy agent_engine \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  --display_name="a2a-demo-orchestrator" \
  ./orchestrator_agent/
```
