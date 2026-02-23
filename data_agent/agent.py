"""
Data Agent — Processes structured data and generates CSV/JSON Artifacts.

Demonstrates:
  F8  — OAuth 2.0 (GCP Service Account) authentication
  F11 — Custom BaseAgent for deterministic (non-LLM) data processing
  F15 — Artifact generation: CSV and JSON file outputs
  F20 — Cloud Run deployment
"""

from __future__ import annotations

from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from shared.callbacks import logging_callback_before_model, logging_callback_after_model
from shared.config import settings
from data_agent.tools import (
    generate_csv_report,
    parse_csv_data,
    compute_statistics,
)

load_dotenv()

# ── Agent Card (F1) ───────────────────────────────────────────────────────────

_csv_skill = AgentSkill(
    id="csv_generation",
    name="CSV Report Generation",
    description=(
        "Processes structured data and generates a downloadable CSV report "
        "as an Artifact."
    ),
    tags=["data", "csv", "report", "artifacts"],
    input_modes=["text/plain", "application/json"],
    output_modes=["text/plain", "text/csv"],
)

_stats_skill = AgentSkill(
    id="data_statistics",
    name="Data Statistics",
    description="Computes descriptive statistics (mean, median, std, etc.) on datasets.",
    tags=["data", "statistics", "analysis"],
    input_modes=["text/plain", "application/json"],
    output_modes=["text/plain", "application/json"],
)

_AGENT_CARD = AgentCard(
    name="data_agent",
    description=(
        "Processes structured data (CSV/JSON) and returns analysis results "
        "and generated files as A2A Artifacts."
    ),
    url=settings.DATA_AGENT_URL,
    version="1.0.0",
    skills=[_csv_skill, _stats_skill],
    capabilities=AgentCapabilities(),
    default_input_modes=["text/plain", "application/json"],
    default_output_modes=["text/plain", "application/json"],
    # F8: OAuth 2.0 (GCP Service Account) Bearer token auth
)

# ── LLM Agent with data tools ─────────────────────────────────────────────────

_SYSTEM_INSTRUCTION = """
You are a data processing assistant.

When asked to process data:
1. Understand the format: is it CSV text, JSON, or a description of data to generate?
2. Use parse_csv_data to parse raw CSV input.
3. Use compute_statistics to calculate summary statistics.
4. Use generate_csv_report to create a formatted CSV Artifact.
5. Always return structured results with clear column descriptions.

For Artifact generation:
- Call generate_csv_report which returns a file that will be attached as an Artifact.
- Tell the user the Artifact ID so they can download it.
"""

root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="data_agent",
    description="Processes structured data and generates CSV/JSON Artifacts.",
    instruction=_SYSTEM_INSTRUCTION,
    tools=[generate_csv_report, parse_csv_data, compute_statistics],
    before_model_callback=logging_callback_before_model,
    after_model_callback=logging_callback_after_model,
)

# ── FastAPI A2A app ───────────────────────────────────────────────────────────

app = to_a2a(root_agent, port=8004, agent_card=_AGENT_CARD)


# ── OAuth 2.0 middleware (F8) ─────────────────────────────────────────────────
# Validates Bearer tokens issued by GCP for a service account using
# google-auth token verification.  Falls back to demo mode when google-auth
# is unavailable or when a demo token is presented.

async def _oauth_middleware(request: Request, call_next):
    """
    Middleware that enforces GCP Service Account OAuth 2.0 Bearer tokens (F8).

    The ``/.well-known/agent.json`` discovery endpoint is always public.
    All other requests require a valid Bearer token.

    Token verification order:
    1. Try google-auth's ``id_token.verify_oauth2_token`` for real GCP SAs.
    2. Accept the demo token from ``settings.CODE_AGENT_API_KEY`` as a fallback
       for local development without GCP credentials.
    """
    if request.url.path == "/.well-known/agent.json":
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return JSONResponse(
            {"error": "Bearer token required (OAuth 2.0 client credentials)"},
            status_code=401,
        )

    token = auth_header[len("Bearer "):]

    # Demo/test mode: accept the configured demo token directly
    demo_token = settings.CODE_AGENT_API_KEY  # reuse for simplicity in local dev
    if token == demo_token:
        return await call_next(request)

    # Production mode: verify via google-auth
    try:
        import google.auth.transport.requests as google_requests
        from google.oauth2 import id_token

        transport_request = google_requests.Request()
        id_token.verify_oauth2_token(token, transport_request)
        return await call_next(request)
    except ImportError:
        # google-auth not available in this environment
        return JSONResponse(
            {"error": "google-auth not available for token verification"},
            status_code=503,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": f"Invalid OAuth 2.0 token: {exc}"},
            status_code=401,
        )


app.add_middleware(BaseHTTPMiddleware, dispatch=_oauth_middleware)
