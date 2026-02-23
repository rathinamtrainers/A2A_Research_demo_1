"""
Weather Agent — A2A server exposing weather lookup via OpenWeatherMap.

Exposes ``root_agent`` for ``adk api_server --a2a`` and also exports
``app`` (the FastAPI application) for direct uvicorn usage.

Features demonstrated:
  F1  — Custom AgentCard with explicit skills and capabilities
  F2  — Synchronous message/send
  F3  — Streaming via SSE (capabilities.streaming=True)
  F8  — No authentication (open / local-dev scheme)
  F12 — Custom function tool: get_weather()
  F20 — Cloud Run deployment via Dockerfile
  F24 — Cross-framework interoperability target
"""

from __future__ import annotations

from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from shared.callbacks import logging_callback_before_tool, logging_callback_after_tool
from shared.config import settings
from weather_agent.tools import get_weather, get_forecast

load_dotenv()

# ── Agent Card (F1 — Discovery & Capability Advertisement) ────────────────────

_weather_skill = AgentSkill(
    id="weather_lookup",
    name="Weather Lookup",
    description="Returns current weather conditions for a given city.",
    tags=["weather", "real-time"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

_forecast_skill = AgentSkill(
    id="weather_forecast",
    name="Weather Forecast",
    description="Returns a 5-day weather forecast for a given city.",
    tags=["weather", "forecast"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

_AGENT_CARD = AgentCard(
    name="weather_agent",
    description="Retrieves real-time weather data and forecasts via OpenWeatherMap.",
    url=settings.WEATHER_AGENT_URL,  # F20 — resolved from env at startup
    version="1.0.0",
    skills=[_weather_skill, _forecast_skill],
    capabilities=AgentCapabilities(streaming=True),  # F3 — SSE streaming supported
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    # F8 — No authentication required for this agent (open / local-dev)
    # securitySchemes: [] (empty list = no auth enforcement)
)

# ── LLM Agent definition ──────────────────────────────────────────────────────

_SYSTEM_INSTRUCTION = """
You are a weather assistant. When a user asks about the weather in a city,
call the get_weather tool to retrieve current conditions.
For multi-day forecasts, call the get_forecast tool.
Always include temperature (°C and °F), conditions, humidity, and wind speed.
"""

root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="weather_agent",
    description="Retrieves real-time weather data and forecasts.",
    instruction=_SYSTEM_INSTRUCTION,
    tools=[get_weather, get_forecast],
    before_tool_callback=logging_callback_before_tool,
    after_tool_callback=logging_callback_after_tool,
)

# ── FastAPI A2A application (F1, F2, F3) ─────────────────────────────────────
# ``to_a2a`` wraps the ADK agent in a FastAPI app that:
#   - Serves /.well-known/agent.json  (Agent Card)
#   - Handles POST /  (JSON-RPC: message/send, message/stream, tasks/*)

app = to_a2a(root_agent, port=8001, agent_card=_AGENT_CARD)
