# research_agent/

Remote A2A agent that performs deep web research using Google Search grounding.
Demonstrates multi-turn interactions (input-required) and tiered capability
disclosure via Extended Agent Cards.

## Features Demonstrated

| Feature | Description |
|---|---|
| F3 — Streaming | Long research responses streamed via SSE |
| F6 — Multi-turn | Pauses with `input-required` when query is ambiguous |
| F7 — Extended Card | Authenticated clients see premium `competitive_analysis` skill |
| F8 — Bearer Auth | JWT Bearer token required for all requests |
| F12 — Built-in Tools | `google_search` tool (Gemini-native Search grounding) |
| F14 — Memory | TODO: Store key facts from sessions for future recall |
| F20 — Cloud Run | Containerised via Dockerfile |

## Files

| File | Purpose |
|---|---|
| `agent.py` | `root_agent` + `app` + public/extended Agent Cards |
| `Dockerfile` | Cloud Run deployment container |

## Running Locally

```bash
adk api_server --a2a --port 8002 ./research_agent/
```

## Authentication

Send a Bearer token in the `Authorization` header:

```bash
# Generate demo token (run from project root):
python -c "from shared.auth import create_bearer_token; print(create_bearer_token('demo'))"

# Use token:
curl -H "Authorization: Bearer <token>" http://localhost:8002/.well-known/agent.json
```
