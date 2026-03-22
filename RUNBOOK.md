# A2A Demo — Start & Test Runbook

## Prerequisites

- Python 3.11+
- `gcloud` CLI authenticated (`gcloud auth list` should show an active account)
- `GOOGLE_CLOUD_PROJECT` environment variable set, or edit `.env` manually

---

## 1. One-Time Setup

```bash
# Create virtual environment
python -m venv .venv

# Create .env from example (replace project ID if needed)
cp .env.example .env
```

Edit `.env` and confirm these values:
```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_LOCATION=us-central1
```

> **Optional:** Add `OPENWEATHERMAP_API_KEY` for live weather data.
> Without it, weather queries return mock/cached results.

Install dependencies:
```bash
.venv/Scripts/pip install -r requirements.txt   # Windows
# .venv/bin/pip install -r requirements.txt     # macOS/Linux
```

---

## 2. Start All Agents

Run each command in a separate terminal (or use `&` to background them).
Always run from the project root with `PYTHONUTF8=1` to avoid Windows encoding errors.

```bash
cd /d/tmp/A2A_Research_demo_1
set -a && source .env && set +a
export PYTHONPATH=$(pwd) PYTHONUTF8=1

# Agent servers
.venv/Scripts/uvicorn weather_agent.agent:app  --host 0.0.0.0 --port 8001 > logs/weather_agent.log 2>&1 &
.venv/Scripts/uvicorn research_agent.agent:app --host 0.0.0.0 --port 8002 > logs/research_agent.log 2>&1 &
.venv/Scripts/uvicorn code_agent.agent:app     --host 0.0.0.0 --port 8003 > logs/code_agent.log 2>&1 &
.venv/Scripts/uvicorn data_agent.agent:app     --host 0.0.0.0 --port 8004 > logs/data_agent.log 2>&1 &
.venv/Scripts/uvicorn async_agent.agent:app    --host 0.0.0.0 --port 8005 > logs/async_agent.log 2>&1 &
.venv/Scripts/uvicorn webhook_server.main:app  --host 0.0.0.0 --port 9000 > logs/webhook_server.log 2>&1 &

# Orchestrator Dev UI (port 8080 avoids conflicts with other local services)
.venv/Scripts/adk web . --port 8080 > logs/orchestrator.log 2>&1 &
```

Wait ~5 seconds, then verify all services are up:
```bash
for port in 8001 8002 8003 8004 8005 9000 8080; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/ 2>/dev/null)
  echo ":$port → $code"
done
```

Expected output (non-200 codes are normal — agents require auth or JSON-RPC):
```
:8001 → 405
:8002 → 401
:8003 → 403
:8004 → 401
:8005 → 405
:9000 → 200
:8080 → 307
```

---

## 3. Open the Dev UI

Navigate to **http://localhost:8080** in your browser.

- Select **`orchestrator_agent`** from the dropdown
- Start a **New Session** (top right)

---

## 4. Manual Tests

### Test 1 — Weather (routes to `weather_agent` :8001)
```
What is the weather in London?
```
Expected: Temperature, humidity, wind speed, conditions.

---

### Test 2 — Code Execution (routes to `code_agent` :8003)
```
Write and run Python code to convert 18.5°C to Fahrenheit
```
Expected: Code snippet + output `65.3`.

---

### Test 3 — Data / CSV (routes to `data_agent` :8004)
```
Generate a CSV of 5 European capitals with their populations
```
Expected: A markdown table or CSV block with city, country, population columns.

---

### Test 4 — Research (routes to `research_agent` :8002)
```
Research the latest developments in the A2A protocol
```
Expected: A structured summary with sources. Takes 10–20 seconds.

---

### Test 5 — Multi-Agent (orchestrator decides routing)
```
Get the weather in Tokyo and write Python code to convert that temperature to Fahrenheit
```
Expected: Orchestrator calls `weather_agent` first, then `code_agent`, combines results.

---

### Test 6 — Async Long-Running Task (routes to `async_agent` :8005)
```
Start a long-running data processing job and notify me when done
```
Expected: Task ID returned immediately; webhook notification delivered to `:9000`.

---

## 5. Inspect Traces

In the Dev UI left panel, click any **Invocation** to expand it.
The **Trace** tab shows:
- Which agent was called
- Tool calls and arguments
- Model tokens used
- Sub-agent transfers

The **State** tab shows session memory across turns.

---

## 6. Verify Agent Cards (curl)

Each agent advertises its capabilities at `/.well-known/agent.json`:

```bash
curl http://localhost:8001/.well-known/agent.json | python -m json.tool
curl http://localhost:8002/.well-known/agent.json | python -m json.tool
curl http://localhost:8003/.well-known/agent.json | python -m json.tool
curl http://localhost:8004/.well-known/agent.json | python -m json.tool
curl http://localhost:8005/.well-known/agent.json | python -m json.tool
```

---

## 7. Stop the App

```bash
for port in 8001 8002 8003 8004 8005 9000 8080; do
  pid=$(netstat -ano | grep ":${port} " | grep LISTENING | awk '{print $5}' | head -1)
  [ -n "$pid" ] && cmd //c "taskkill /PID $pid /F" && echo "Stopped :$port"
done
```

---

## Known Issues & Fixes

| Issue | Cause | Fix |
|---|---|---|
| `charmap codec can't encode character` | Windows console encoding | Always export `PYTHONUTF8=1` before starting |
| `No agents found in current folder` | Wrong path passed to `adk web` | Run `adk web .` from project root, not `adk web ./orchestrator_agent/` |
| `[Errno 10048] only one usage of each socket address` | Old process still on port | Find PID with `netstat -ano` and kill with `taskkill /PID <pid> /F` |
| 502 errors in orchestrator log | OpenTelemetry can't reach GCP metrics endpoint | Harmless — background telemetry only |
| Weather agent returns error | Missing API key | Add `OPENWEATHERMAP_API_KEY` to `.env` |
