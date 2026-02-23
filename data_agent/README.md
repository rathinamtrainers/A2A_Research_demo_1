# data_agent/

Remote A2A agent that processes structured data (CSV/JSON) and generates
downloadable file Artifacts. Protected by OAuth 2.0 (GCP Service Account).

## Features Demonstrated

| Feature | Description |
|---|---|
| F8 — OAuth 2.0 | GCP Service Account client credentials flow |
| F11 — Custom Agent | LlmAgent with deterministic data processing tools |
| F15 — Artifacts | `generate_csv_report` produces a `text/csv` file Artifact |
| F20 — Cloud Run | Containerised via Dockerfile |

## Files

| File | Purpose |
|---|---|
| `agent.py` | `root_agent` + `app` with OAuth middleware (TODO) |
| `tools.py` | `parse_csv_data`, `compute_statistics`, `generate_csv_report` |
| `Dockerfile` | Cloud Run deployment container |

## Running Locally

```bash
adk api_server --a2a --port 8004 ./data_agent/
```
