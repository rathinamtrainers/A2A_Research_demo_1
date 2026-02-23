# Environment Setup — A2A Protocol Demo

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ (3.11 recommended) | 3.10 works; 3.11 required for GCP Vertex AI Agent Engine |
| pip | 24+ | Upgraded automatically by setup |
| gcloud CLI | latest | Required for GCP auth and deployment |

> **Python 3.10 warning:** Google libraries will drop Python 3.10 support when it reaches EOL (2026-10-04). Upgrade to 3.11+ for GCP production use.

---

## 1. Activate the Virtual Environment

```bash
# From the project root directory:
source .venv/bin/activate

# Verify you are in the venv:
which python   # should show .../test2/.venv/bin/python
python --version
```

To deactivate:
```bash
deactivate
```

---

## 2. Install Dependencies

The virtual environment is already set up. To reinstall from scratch:

```bash
# Create fresh venv
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip toolchain
pip install --upgrade pip setuptools wheel

# Install all dependencies (uses corrected versions — see note below)
pip install -r requirements.txt
```

### About requirements.txt vs requirements-lock.txt

| File | Purpose |
|---|---|
| `requirements.txt` | Primary packages with pinned versions (human-readable, install this) |
| `requirements-lock.txt` | Full `pip freeze` output — all transitive deps pinned for exact reproducibility |

> **Version correction note:** The spec in `research.md` listed stale versions for several
> transitive dependencies. The following were updated to resolve conflicts with
> `google-adk 1.25.1` and `a2a-sdk 0.3.x`:
>
> | Package | Spec version | Actual working version | Reason |
> |---|---|---|---|
> | `fastapi` | 0.115.12 | 0.131.0 | google-adk requires >=0.124.1 |
> | `google-auth` | 2.38.0 | 2.48.0 | google-adk requires >=2.47.0 |
> | `google-cloud-aiplatform` | 1.112.0 | 1.138.0 | google-adk requires >=1.132.0 |
> | `google-cloud-storage` | 2.18.2 | 3.9.0 | google-adk pulls 3.x |
> | `a2a-sdk` | 0.3.0 | 0.3.24 | google-adk[a2a] requires >=0.3.4 |
> | `pydantic` | 2.11.1 | 2.12.5 | a2a-sdk requires >=2.11.3 |
> | `protobuf` | 5.29.4 | 5.29.6 | a2a-sdk requires >=5.29.5 |
> | `anyio` | 4.9.0 | 4.12.1 | google-adk requires >=4.9.0 |
> | `google-auth-httplib2` | 0.2.0 | 0.3.0 | Pulled by updated google-auth |

---

## 3. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

### Required Variables

| Variable | Description | Required For |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | GCP Project ID | All Vertex AI features |
| `GOOGLE_CLOUD_LOCATION` | GCP region (e.g. `us-central1`) | Vertex AI + Cloud Run |
| `GOOGLE_GENAI_USE_VERTEXAI` | Set to `1` to use Vertex AI (vs AI Studio) | Vertex AI mode |
| `VERTEXAI_STAGING_BUCKET` | GCS bucket for Agent Engine staging | Deployment |
| `GOOGLE_API_KEY` | Google AI Studio API key | Local dev without Vertex AI |

### Optional / Local Dev Variables

| Variable | Description | Default |
|---|---|---|
| `WEATHER_AGENT_URL` | Weather agent A2A endpoint | `http://localhost:8001` |
| `RESEARCH_AGENT_URL` | Research agent A2A endpoint | `http://localhost:8002` |
| `CODE_AGENT_URL` | Code agent A2A endpoint | `http://localhost:8003` |
| `DATA_AGENT_URL` | Data agent A2A endpoint | `http://localhost:8004` |
| `ASYNC_AGENT_URL` | Async agent A2A endpoint | `http://localhost:8005` |
| `WEBHOOK_SERVER_URL` | Webhook receiver URL | `http://localhost:9000` |
| `WEBHOOK_AUTH_TOKEN` | Token for webhook auth demo | — |
| `CODE_AGENT_API_KEY` | API key for code_agent auth demo | — |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry collector endpoint | GCP Telemetry |

---

## 4. GCP Authentication

```bash
# Application Default Credentials (for local dev)
gcloud auth application-default login

# Set default project
gcloud config set project $GOOGLE_CLOUD_PROJECT

# Verify ADC works
gcloud auth application-default print-access-token
```

---

## 5. Verification Commands

Run these after activating the venv to confirm the setup is working:

```bash
# Activate venv first
source .venv/bin/activate

# --- Core package checks ---
python -c "import google.adk; print('google-adk:', google.adk.__version__)"
python -c "import a2a; print('a2a-sdk: OK')"
python -c "import fastapi; print('fastapi:', fastapi.__version__)"
python -c "import uvicorn; print('uvicorn:', uvicorn.__version__)"
python -c "import httpx; print('httpx:', httpx.__version__)"
python -c "import pydantic; print('pydantic:', pydantic.__version__)"
python -c "import grpc; print('grpcio:', grpc.__version__)"
python -c "import google.cloud.aiplatform; print('aiplatform:', google.cloud.aiplatform.__version__)"
python -c "import google.cloud.storage; print('cloud-storage: OK')"
python -c "import dotenv; print('python-dotenv: OK')"
python -c "import rich; print('rich: OK')"
python -c "import typer; print('typer: OK')"
python -c "import pytest; print('pytest:', pytest.__version__)"

# --- ADK CLI check ---
adk --version

# --- Run tests ---
pytest --version
```

### Expected output (verified on this machine):

```
google-adk:  1.25.1
a2a-sdk:     OK
fastapi:     0.131.0
uvicorn:     0.34.0
httpx:       0.28.1
pydantic:    2.12.5
grpcio:      1.71.0
aiplatform:  1.138.0
cloud-storage: OK
python-dotenv: OK
rich:        OK
typer:       OK
pytest:      8.3.5
```

---

## 6. Starting the Demo (Quick Start)

```bash
# 1. Activate venv and load env
source .venv/bin/activate
cp .env.example .env  # edit with your values

# 2. Start individual A2A agent servers (separate terminals)
adk api_server --a2a --port 8001 ./weather_agent/
adk api_server --a2a --port 8002 ./research_agent/
adk api_server --a2a --port 8003 ./code_agent/
adk api_server --a2a --port 8004 ./data_agent/
uvicorn async_agent.agent:app --port 8005

# 3. Start webhook receiver
uvicorn webhook_server.main:app --port 9000

# 4. Launch orchestrator in browser UI
adk web ./orchestrator_agent/
# → open http://localhost:8000
```

---

## 7. GCP APIs to Enable

Before deploying to GCP:

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  cloudresourcemanager.googleapis.com \
  secretmanager.googleapis.com
```

Create staging bucket:
```bash
gcloud storage buckets create gs://${GOOGLE_CLOUD_PROJECT}-a2a-demo \
  --location=us-central1
```
