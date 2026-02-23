# weather_agent/

Remote A2A agent that exposes weather lookup and forecast capabilities via
the OpenWeatherMap API. This is the simplest agent in the demo — it has no
authentication requirement (open access).

## Features Demonstrated

| Feature | Description |
|---|---|
| F1 — Agent Card | Custom `AgentCard` with `weather_lookup` and `weather_forecast` skills |
| F2 — Sync Request | Answers weather queries via `message/send` |
| F3 — Streaming | SSE streaming enabled (`capabilities.streaming=True`) |
| F8 — No-auth | Open access for local development |
| F12 — Function Tools | `get_weather()` and `get_forecast()` tools |
| F20 — Cloud Run | Containerised via Dockerfile |
| F24 — Interop | Primary target for the standalone `a2a_client` demo |

## Files

| File | Purpose |
|---|---|
| `agent.py` | `root_agent` + `app` (FastAPI A2A server) |
| `tools.py` | `get_weather`, `get_forecast` with OpenWeatherMap + mock fallback |
| `Dockerfile` | Cloud Run deployment container |

## Running Locally

```bash
# Via ADK (recommended for development):
adk api_server --a2a --port 8001 ./weather_agent/

# Via uvicorn directly:
uvicorn weather_agent.agent:app --port 8001

# Verify Agent Card:
curl http://localhost:8001/.well-known/agent.json | jq
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENWEATHERMAP_API_KEY` | No | Real weather data; mock used if absent |
| `GEMINI_MODEL` | No | Defaults to `gemini-2.0-flash` |
