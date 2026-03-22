# A2A Demo — Start & Test Runbook

## Prerequisites

- Python 3.11+
- `gcloud` CLI authenticated (`gcloud auth list` should show an active account)
- `GOOGLE_CLOUD_PROJECT` environment variable set, or edit `.env` manually

---

## 1. One-Time Setup

```powershell
# Create virtual environment
python -m venv .venv

# Create .env from example (replace project ID if needed)
Copy-Item .env.example .env
```

Edit `.env` and confirm these values:
```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_LOCATION=us-central1
```

> **Optional:** Add `OPENWEATHERMAP_API_KEY` for live weather data.
> Without it, weather queries will fail.

Install dependencies:
```powershell
.venv\Scripts\pip install -r requirements.txt
```

---

## 2. Ensure Ports Are Free

Before starting, check and clear all required ports:

```powershell
$ports = @{8001="weather_agent"; 8002="research_agent"; 8003="code_agent"; 8004="data_agent"; 8005="async_agent"; 9000="webhook_server"; 8080="orchestrator"}

foreach ($port in $ports.Keys | Sort-Object) {
    $conn = netstat -ano | Select-String ":$port " | Select-String "LISTENING"
    if ($conn) {
        $pid = ($conn.ToString().Trim() -split '\s+')[-1]
        taskkill /PID $pid /F | Out-Null
        Write-Host "Killed :$port (PID $pid)"
    } else {
        Write-Host ":$port is free"
    }
}
```

---

## 3. Start All Agents

Run from the project root:

```powershell
.\scripts\start_all.ps1
```

This script:
- Loads `.env` automatically
- Sets `PYTHONUTF8=1` (prevents Windows encoding errors)
- Starts all 7 services in the background
- Runs a health check after 5 seconds

**Services started:**

| Port | Service |
|------|---------|
| 8001 | weather_agent |
| 8002 | research_agent |
| 8003 | code_agent |
| 8004 | data_agent |
| 8005 | async_agent |
| 9000 | webhook_server |
| 8080 | orchestrator (ADK Dev UI) |

Logs are written to the `logs\` directory.

---

## 4. Open the Dev UI

Navigate to **http://localhost:8080** in your browser.

- Select **`orchestrator_agent`** from the dropdown
- Click **+ New Session** (top right)

---

## 5. Manual Tests

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

## 6. Inspect Traces

In the Dev UI left panel, click any **Invocation** to expand it.
The **Trace** tab shows:
- Which agent was called
- Tool calls and arguments
- Model tokens used
- Sub-agent transfers

The **State** tab shows session memory across turns.

---

## 7. Verify Agent Cards

Each agent advertises its capabilities at `/.well-known/agent.json`:

```powershell
foreach ($port in 8001,8002,8003,8004,8005) {
    Write-Host "--- :$port ---"
    Invoke-RestMethod "http://localhost:$port/.well-known/agent.json" | ConvertTo-Json
}
```

---

## 8. Stop the App

```powershell
.\scripts\stop_all.ps1
```

Or manually kill a specific port:
```powershell
$conn = netstat -ano | Select-String ":8080 " | Select-String "LISTENING"
$pid = ($conn.ToString().Trim() -split '\s+')[-1]
taskkill /PID $pid /F
```

---

## Known Issues & Fixes

| Issue | Cause | Fix |
|---|---|---|
| `charmap codec can't encode character` | Windows console encoding | `start_all.ps1` sets `PYTHONUTF8=1` automatically |
| `No agents found in current folder` | Wrong path passed to `adk web` | Scripts use `adk web .` from project root |
| Port already in use | Previous run not stopped cleanly | Run step 2 (Ensure Ports Are Free) before starting |
| 502 errors in orchestrator log | OpenTelemetry can't reach GCP metrics endpoint | Harmless — background telemetry only |
| Weather agent returns error | Missing API key | Add `OPENWEATHERMAP_API_KEY` to `.env` |
