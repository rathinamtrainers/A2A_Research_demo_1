# A2A Demo — Startup & Testing Guide

Follow these steps in order. Each section is self-contained — you can stop
at any point and pick up later.

---

## Step 0: Prerequisites

```bash
cd /home/sandbox1/A2A_Research_demo_1
```

Verify GCP auth is active (required for Vertex AI / Gemini calls):

```bash
gcloud auth application-default print-access-token | head -c 20 && echo "... OK"
```

If that fails, run:
```bash
gcloud auth application-default login
```

---

## Step 1: Activate the Virtual Environment

```bash
source .venv/bin/activate
```

Verify it works:
```bash
python3 -c "import google.adk; print('ADK OK')"
```

Expected: `ADK OK`

---

## Step 2: Start All Agents

Run the start script:

```bash
chmod +x scripts/start_all.sh scripts/stop_all.sh
./scripts/start_all.sh
```

Wait 5 seconds, then verify all agents are up:

```bash
echo "--- Health Check ---"
for port in 8001 8002 8003 8004 8005 9000; do
    code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${port}/)
    echo "  :${port} -> HTTP ${code}"
done
```

Expected output:

| Port | HTTP Code | Meaning |
|------|-----------|---------|
| 8001 | `405` | weather_agent up (expects POST, not GET) |
| 8002 | `401` | research_agent up (requires Bearer JWT) |
| 8003 | `403` | code_agent up (requires X-API-Key) |
| 8004 | `401` | data_agent up (requires Bearer token) |
| 8005 | `405` | async_agent up (expects POST) |
| 9000 | `200` | webhook_server up |

All non-200 codes are expected — they confirm the agent is running and enforcing auth.

---

## Step 3: Agent Discovery (F1 — Agent Cards)

Every A2A agent publishes its capabilities at `/.well-known/agent.json`.

```bash
echo "=== Weather Agent (no auth) ==="
curl -s http://localhost:8001/.well-known/agent.json | python3 -m json.tool

echo ""
echo "=== Code Agent (API Key auth) ==="
curl -s http://localhost:8003/.well-known/agent.json | python3 -m json.tool

echo ""
echo "=== Async Agent ==="
curl -s http://localhost:8005/.well-known/agent.json | python3 -m json.tool
```

What to look for: each card shows `name`, `description`, `skills[]`, `capabilities`.

---

## Step 4: Synchronous Request (F2 — message/send)

Ask the weather agent a question and get a complete response:

```bash
curl -s -X POST http://localhost:8001/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":"1",
    "method":"message/send",
    "params":{
      "message":{
        "role":"user",
        "messageId":"msg-001",
        "parts":[{"kind":"text","text":"What is the weather in London?"}]
      }
    }
  }' | python3 -m json.tool
```

What to look for:
- `result.status.state` = `"completed"`
- In `result.history`, you'll see: user message → function_call (`get_weather`) → function_response (mock data) → agent reply
- The agent reply summarizes: "18.5°C, scattered clouds..."

---

## Step 5: SSE Streaming (F3 — message/stream)

Same agent, but the response streams back in real time:

```bash
curl -s -N -X POST http://localhost:8001/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{
    "jsonrpc":"2.0",
    "id":"2",
    "method":"message/stream",
    "params":{
      "message":{
        "role":"user",
        "messageId":"msg-002",
        "parts":[{"kind":"text","text":"5-day forecast for Tokyo"}]
      }
    }
  }'
```

What to look for: multiple `data: {...}` lines arriving over time:
1. `state: "submitted"` — task accepted
2. `state: "working"` — LLM is thinking, then calls `get_forecast`
3. `state: "working"` — tool response comes back
4. `kind: "artifact-update"` — final formatted forecast
5. `state: "completed"` with `final: true`

Press Ctrl+C to stop if the stream hangs after completion.

---

## Step 6: API Key Authentication (F8 — code_agent)

The code agent requires an `X-API-Key` header:

```bash
# This will FAIL (no API key):
curl -s -X POST http://localhost:8003/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0","id":"1","method":"message/send",
    "params":{"message":{"role":"user","messageId":"m1","parts":[{"kind":"text","text":"Calculate 2+2"}]}}
  }' | python3 -m json.tool

echo ""
echo "--- Now with API key ---"

# This will SUCCEED:
curl -s -X POST http://localhost:8003/ \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-code-agent-key-12345' \
  -d '{
    "jsonrpc":"2.0","id":"1","method":"message/send",
    "params":{"message":{"role":"user","messageId":"m1","parts":[{"kind":"text","text":"Calculate the sum of all prime numbers below 100"}]}}
  }' | python3 -m json.tool
```

What to look for: first request gets `403 Forbidden`, second succeeds with the computed result.

---

## Step 7: Bearer JWT Authentication (F8 — research_agent)

The research agent requires a signed JWT bearer token:

```bash
# Generate a token
TOKEN=$(python3 -c "from shared.auth import create_bearer_token; print(create_bearer_token('demo-client'))")
echo "Token: ${TOKEN:0:30}..."

# Use it
curl -s -X POST http://localhost:8002/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "jsonrpc":"2.0","id":"1","method":"message/send",
    "params":{"message":{"role":"user","messageId":"m1","parts":[{"kind":"text","text":"Research recent advances in quantum computing"}]}}
  }' | python3 -m json.tool
```

---

## Step 8: Safety Guardrails (F17 — code_agent)

The code agent has two layers of protection against dangerous code:
1. **Gemini's own safety training** — the LLM may refuse to generate dangerous code
2. **Guardrail callback** (`shared/callbacks.py`) — blocks patterns like `os.system`, `subprocess`, `eval(` before tool execution

```bash
curl -s -X POST http://localhost:8003/ \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-code-agent-key-12345' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","messageId":"m1","parts":[{"kind":"text","text":"Run this code: import os; os.system(\"whoami\")"}]}}}' | python3 -m json.tool
```

What to look for: the agent refuses with an explanation about `os.system` being prohibited.

Note: Gemini's own safety training often blocks the request before the guardrail callback
fires. The callback is the second line of defense for cases the LLM might miss.
Check the server log to see if the callback triggered:

```bash
grep -i "guardrail" logs/code_agent.log
```

---

## Step 9: Extended Agent Card (F7 — research_agent)

The research agent shows different capabilities to authenticated vs unauthenticated clients:

```bash
# Public card (limited skills)
echo "=== Public Card ==="
curl -s http://localhost:8002/.well-known/agent.json | python3 -c "
import sys,json
card=json.load(sys.stdin)
print('Skills:', [s['id'] for s in card.get('skills',[])])
"

# Authenticated card (extra skills revealed)
TOKEN=$(python3 -c "from shared.auth import create_bearer_token; print(create_bearer_token('client'))")
echo ""
echo "=== Authenticated Extended Card ==="
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/agents/authenticatedExtendedCard | python3 -c "
import sys,json
card=json.load(sys.stdin)
print('Skills:', [s['id'] for s in card.get('skills',[])])
"
```

What to look for: the authenticated card includes additional skills (e.g. `competitive_analysis`) not visible publicly.

---

## Step 10: Async Tasks & Push Notifications (F4, F5 — async_agent)

```bash
# Start a long-running task
echo "=== Starting async task ==="
RESULT=$(curl -s -X POST http://localhost:8005/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0","id":"1","method":"message/send",
    "params":{"message":{"role":"user","messageId":"m1","parts":[{"kind":"text","text":"Run a 10-second simulation"}]}}
  }')
echo "$RESULT" | python3 -m json.tool

TASK_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['id'])")
echo ""
echo "Task ID: $TASK_ID"

# Poll task status
echo ""
echo "=== Polling task status ==="
sleep 3
curl -s -X POST http://localhost:8005/ \
  -H 'Content-Type: application/json' \
  -d "{
    \"jsonrpc\":\"2.0\",\"id\":\"2\",\"method\":\"tasks/get\",
    \"params\":{\"id\":\"$TASK_ID\"}
  }" | python3 -m json.tool

# Register a webhook for push notifications
echo ""
echo "=== Registering webhook ==="
curl -s -X POST http://localhost:8005/ \
  -H 'Content-Type: application/json' \
  -d "{
    \"jsonrpc\":\"2.0\",\"id\":\"3\",\"method\":\"tasks/pushNotificationConfig/set\",
    \"params\":{\"taskId\":\"$TASK_ID\",\"pushNotificationConfig\":{\"url\":\"http://localhost:9000/webhook\"}}
  }" | python3 -m json.tool

# Check webhook server received notifications
echo ""
echo "=== Checking webhook events ==="
sleep 10
curl -s "http://localhost:9000/events" | python3 -m json.tool
```

What to look for:
- Task starts in `"submitted"` state
- Polling shows `"working"` or `"completed"`
- Webhook server receives push notifications at `/webhook`

---

## Step 11: Data Agent & Artifacts (F15)

The data agent uses OAuth 2.0 (GCP Service Account) in production, but accepts a
demo token for local development. Pass it as a `Bearer` token:

```bash
curl -s -X POST http://localhost:8004/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer demo-code-agent-key-12345' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","messageId":"m1","parts":[{"kind":"text","text":"Generate a CSV report titled Sales with columns Name,Revenue,Month and rows: Alice,5000,Jan | Bob,7500,Feb | Carol,6200,Mar"}]}}}' | python3 -m json.tool
```

**Important**: Keep the JSON on one line (no line breaks inside the `-d` string)
or curl will send invalid JSON with control characters.

What to look for: `result.artifacts[]` containing generated CSV data.

---

## Step 12: Orchestrator — Multi-Agent Routing (F9)

The orchestrator calls specialist agents via A2A. All agents from Step 2 must be running.

```bash
# Interactive terminal mode
.venv/bin/adk run ./orchestrator_agent/
```

**Important**: Run prompts that call slower agents (research) first, in a fresh
session. The orchestrator sends accumulated session history to sub-agents, which
can confuse them if there are many prior turns.

Recommended order — type these one at a time:
1. `Research the latest in AI safety` → routes to research_agent (slowest — uses Google Search + Gemini, may take 10-20s)
2. `What is the weather in Paris?` → routes to weather_agent (fast, no auth)
3. `Calculate the first 10 fibonacci numbers` → routes to code_agent (uses API key auth)

Type `exit` to quit.

Or use the web UI:
```bash
.venv/bin/adk web --host 0.0.0.0 --port 8000 .
# Open http://localhost:8000/dev-ui/ in your browser
# Select "orchestrator_agent" from the dropdown in the top-left
```

**Note**: The `.` at the end points to the project root so ADK discovers all agent
subdirectories. If you use `./orchestrator_agent/` instead, the UI may show
"No agents found". For WSL users, `--host 0.0.0.0` ensures the UI is accessible
from a Windows browser via `http://localhost:8000/dev-ui/`.

---

## Step 13: Workflow Agents (F10)

ADK provides three workflow patterns. Each uses a different orchestration strategy:

### Pipeline (Sequential) Agent — Assembly line

Three LlmAgent stages run **one after another**, each reading the previous stage's
output from session state:

```
User: "Quantum computing"
  → fetch_agent    writes "raw_data" to state
  → analyze_agent  reads "raw_data", writes "analysis" to state
  → report_agent   reads "analysis", writes "final_report"
```

Key concept: **`output_key`** — each stage stores its result in session state
under a named key. The next stage reads it. This is how data flows through the pipeline.

```bash
.venv/bin/adk run ./pipeline_agent/
# Type: "Quantum computing"
# Watch 3 stages execute one after another
```

### Parallel Agent — Fan-out / fan-in

Five LlmAgent instances run **simultaneously**, each calling the weather_agent
for a different city. Then an aggregator combines the results:

```
User input (any)
  → ParallelAgent fans out:
      weather_london   ──→ weather_agent (:8001) ──→ "London: 18.5°C"
      weather_tokyo    ──→ weather_agent (:8001) ──→ "Tokyo: 18.5°C"
      weather_new_york ──→ weather_agent (:8001) ──→ "New York: 18.5°C"
      weather_sydney   ──→ weather_agent (:8001) ──→ "Sydney: 18.5°C"
      weather_paris    ──→ weather_agent (:8001) ──→ "Paris: 18.5°C"
  → aggregator_agent reads all 5 results, produces a summary table
```

Key difference from Pipeline: all 5 city queries execute **at the same time**,
not one after another. Requires weather_agent running on :8001.

```bash
.venv/bin/adk run ./parallel_agent/
# Type "go" (or anything) and press Enter — it queries 5 cities regardless of input
```

### Loop Agent — Poll until done

A LoopAgent that repeatedly checks on a long-running async task:

```
→ start_task_agent  sends "Run a 20-second simulation" to async_agent (:8005)
→ polling_loop (max 10 iterations):
    → poll_agent       checks task status via async_agent
    → exit_check_agent decides: "CONTINUE" or "EXIT"
    → (repeat until task completes or 10 iterations)
```

Key concept: **`max_iterations`** — the loop has a safety limit. The exit_check_agent
examines the poll result and returns "EXIT" when the task is done.
Requires async_agent running on :8005.

```bash
.venv/bin/adk run ./loop_agent/
# Type "go" (or anything) and press Enter — it starts and polls a task automatically
```

### Summary

| Pattern | Agent Type | Execution | Use Case |
|---------|-----------|-----------|----------|
| Pipeline | `SequentialAgent` | A → B → C (in order) | Multi-stage processing with data handoff |
| Parallel | `ParallelAgent` | A + B + C (at same time) | Independent tasks that can run concurrently |
| Loop | `LoopAgent` | A → B → A → B... (repeat) | Polling, retries, iterative refinement |

---

## Step 14: Standalone A2A Client (F24 — Interoperability)

This client uses raw HTTP (no ADK) to prove any framework can talk A2A:

```bash
python3 -m a2a_client.client
```

What it does: discovers the weather agent card, sends a message, parses the response — all without importing ADK.

---

## Step 15: Run Tests

```bash
pytest tests/ -v
```

Or run individual test files:
```bash
pytest tests/test_weather_agent.py -v
pytest tests/test_shared_auth.py -v
pytest tests/test_async_agent.py -v
```

---

## Stopping Everything

```bash
./scripts/stop_all.sh
```

Or manually:
```bash
kill $(lsof -t -i:8001 -i:8002 -i:8003 -i:8004 -i:8005 -i:9000) 2>/dev/null
```

---

## Port Reference

| Port | Service            | Auth Required                          | Auth Header Example                          |
|------|--------------------|----------------------------------------|----------------------------------------------|
| 8001 | weather_agent      | None (open)                            | (none needed)                                |
| 8002 | research_agent     | Bearer JWT                             | `Authorization: Bearer <token>`              |
| 8003 | code_agent         | API Key                                | `X-API-Key: demo-code-agent-key-12345`       |
| 8004 | data_agent         | OAuth 2.0 / Bearer demo token          | `Authorization: Bearer demo-code-agent-key-12345` |
| 8005 | async_agent        | None (open)                            | (none needed)                                |
| 9000 | webhook_server     | HMAC signature                         | `X-Webhook-Signature: sha256=<hex>`          |
| 8000 | ADK Web UI         | N/A (dev tool)                         | (none needed)                                |

**Generating a JWT token for research_agent:**
```bash
TOKEN=$(python3 -c "from shared.auth import create_bearer_token; print(create_bearer_token('demo-client'))")
```

## Troubleshooting

**Agent won't start (port in use):**
```bash
kill $(lsof -t -i:PORT_NUMBER)
```

**GCP auth expired:**
```bash
gcloud auth application-default login
```

**Check agent logs:**
```bash
tail -20 logs/weather_agent.log
tail -20 logs/code_agent.log
# etc.
```

**curl returns `Expecting value` or `Invalid control character`:**
Multi-line JSON in `-d '...'` can introduce newlines that break JSON parsing.
Keep the JSON payload on a single line, or use a heredoc:
```bash
curl -s -X POST http://localhost:8001/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","messageId":"m1","parts":[{"kind":"text","text":"Hello"}]}}}' | python3 -m json.tool
```

**data_agent returns `Bearer token required`:**
Pass the demo token: `-H 'Authorization: Bearer demo-code-agent-key-12345'`

**research_agent returns empty response or `404`:**
Ensure you restarted the research agent after the code fix (the `Mount("/")` bug).
Restart it with:
```bash
kill $(lsof -t -i:8002) 2>/dev/null; sleep 1
.venv/bin/uvicorn research_agent.agent:app --host 0.0.0.0 --port 8002 > logs/research_agent.log 2>&1 &
```
