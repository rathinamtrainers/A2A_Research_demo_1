# parallel_agent/

A `ParallelAgent` that fans out weather queries for 5 cities concurrently,
then an aggregator summarises all results.

## Features Demonstrated

| Feature | Description |
|---|---|
| F10 — ParallelAgent | All 5 city sub-agents run concurrently (fan-out) |
| F9 — A2A Routing | Each city agent delegates to the remote `weather_agent` |

## Architecture

```
SequentialAgent (root_agent)
  ├── ParallelAgent (parallel_weather)   ← runs all 5 simultaneously
  │     ├── weather_London
  │     ├── weather_Tokyo
  │     ├── weather_New_York
  │     ├── weather_Sydney
  │     └── weather_Paris
  └── LlmAgent (aggregator)              ← reads all 5 results from state
```

## Running Locally

```bash
# Requires weather_agent running at http://localhost:8001
adk api_server --a2a --port 8001 ./weather_agent/

adk run ./parallel_agent/
```
