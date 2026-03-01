"""
Research Agent — Deep research using Google Search grounding.

Demonstrates:
  F3  — SSE streaming (long research responses streamed in chunks)
  F6  — Multi-turn / input-required (pauses for ambiguous queries)
  F7  — Extended Agent Card (authenticated clients see premium skills)
  F8  — Bearer token (JWT) authentication
  F12 — Built-in google_search tool
  F14 — Memory: stores key facts for recall in future sessions
  F20 — Cloud Run deployment
"""

from __future__ import annotations

from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from shared.auth import verify_bearer_token
from shared.callbacks import logging_callback_before_model, logging_callback_after_model
from shared.config import settings

load_dotenv()

# ── Agent Card (F1) ───────────────────────────────────────────────────────────

_research_skill = AgentSkill(
    id="web_research",
    name="Web Research",
    description=(
        "Performs deep research using Google Search with real-time grounding. "
        "Returns a structured research report with citations."
    ),
    tags=["research", "search", "grounding"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

_extended_skill = AgentSkill(
    id="competitive_analysis",
    name="Competitive Analysis",
    description=(
        "[PREMIUM] Deep competitive analysis with multi-source synthesis. "
        "Only available to authenticated clients."
    ),
    tags=["research", "competitive-analysis", "premium"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

# Public card — shown to unauthenticated clients
_PUBLIC_AGENT_CARD = AgentCard(
    name="research_agent",
    description="Performs deep research using Google Search grounding.",
    url=settings.RESEARCH_AGENT_URL,
    version="1.0.0",
    skills=[_research_skill],
    capabilities=AgentCapabilities(streaming=True),  # F3 — SSE streaming
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
)

# Authenticated extended card — shown after Bearer token verification (F7)
_EXTENDED_AGENT_CARD = AgentCard(
    name="research_agent",
    description="Performs deep research using Google Search grounding. (Authenticated)",
    url=settings.RESEARCH_AGENT_URL,
    version="1.0.0",
    skills=[_research_skill, _extended_skill],
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
)

# ── LLM Agent ─────────────────────────────────────────────────────────────────

_SYSTEM_INSTRUCTION = """
You are a research assistant with access to Google Search.

When a user asks a research question:
1. Use the google_search tool to gather current information.
2. Synthesise findings into a clear, structured report.
3. If the query is ambiguous or missing key parameters (e.g., "research AI"
   without specifying a focus area), respond with status input-required and
   ask the user to clarify before proceeding.
4. Always cite your sources.

For competitive analysis requests (premium tier):
- Perform multi-source deep research.
- Structure output as: Executive Summary, Key Players, Market Trends,
  SWOT Analysis, Recommendations.
"""

root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="research_agent",
    description="Deep research agent powered by Google Search grounding.",
    instruction=_SYSTEM_INSTRUCTION,
    tools=[google_search],
    before_model_callback=logging_callback_before_model,
    after_model_callback=logging_callback_after_model,
)

# ── Runner with memory service (F14) ─────────────────────────────────────────
# Inject an InMemoryMemoryService so the agent can recall facts across sessions.
# Pass this runner to to_a2a() so it uses our pre-configured services.

_memory_service = InMemoryMemoryService()

_runner = Runner(
    app_name=root_agent.name,
    agent=root_agent,
    session_service=InMemorySessionService(),
    memory_service=_memory_service,
)

# ── A2A Starlette app (F1, F2, F3) ───────────────────────────────────────────

_a2a_app = to_a2a(root_agent, port=8002, agent_card=_PUBLIC_AGENT_CARD, runner=_runner)

# ── Extended Agent Card route (F7) ────────────────────────────────────────────


async def _authenticated_extended_card(request: Request) -> Response:
    """
    Return the extended Agent Card for authenticated clients (F7).

    Requires a valid Bearer token in the ``Authorization`` header.
    On success returns ``_EXTENDED_AGENT_CARD`` which includes the
    premium ``competitive_analysis`` skill.

    Returns:
        200 with the extended Agent Card JSON, or 401 on auth failure.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return JSONResponse(
            {"error": "Bearer token required"},
            status_code=401,
        )
    token = auth_header[len("Bearer "):]

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    creds = HTTPAuthorizationCredentials(scheme="bearer", credentials=token)
    try:
        verify_bearer_token(credentials=creds)
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    return JSONResponse(_EXTENDED_AGENT_CARD.model_dump(exclude_none=True))


# ── Bearer token middleware (F8) ─────────────────────────────────────────────
# Protect all endpoints except /.well-known/agent.json (discovery must be public)
# and /agents/authenticatedExtendedCard (manages its own auth).

_OPEN_PATHS = frozenset({
    "/.well-known/agent.json",
    "/agents/authenticatedExtendedCard",
})


async def _bearer_auth_middleware(request: Request, call_next):
    """
    Enforce Bearer JWT authentication on all protected endpoints (F8).

    Allows the public discovery endpoint and the authenticated extended
    card route to handle their own auth or remain open.
    """
    if request.url.path in _OPEN_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return JSONResponse(
            {"error": "Bearer token required"},
            status_code=401,
        )
    token = auth_header[len("Bearer "):]

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    creds = HTTPAuthorizationCredentials(scheme="bearer", credentials=token)
    try:
        verify_bearer_token(credentials=creds)
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    return await call_next(request)


# ── Compose final app with extra route (F7) ───────────────────────────────────
# Add the extended card route directly to the a2a app, then add auth middleware.
# NOTE: We add routes to _a2a_app directly instead of wrapping it in an outer
# Starlette via Mount, because Starlette does not propagate startup events to
# mounted sub-apps — and to_a2a() registers its A2A routes during startup.

_a2a_app.add_route(
    "/agents/authenticatedExtendedCard",
    _authenticated_extended_card,
    methods=["GET"],
)

app = _a2a_app

# Add Bearer auth middleware (F8) — added after construction so the middleware
# stack is rebuilt on the next request, wrapping all routes.
app.add_middleware(BaseHTTPMiddleware, dispatch=_bearer_auth_middleware)
