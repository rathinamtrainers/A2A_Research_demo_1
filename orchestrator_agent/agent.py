"""
Orchestrator Agent — Root LLM agent that routes to specialist A2A agents.

This module exposes ``root_agent`` which is the entry-point used by:
  - ``adk run ./orchestrator_agent/``
  - ``adk web ./orchestrator_agent/``
  - ``adk deploy agent_engine ./orchestrator_agent/``

Features demonstrated:
  F9  — Agent-to-Agent routing via RemoteA2aAgent sub-agents
  F11 — LlmAgent backed by Gemini 2.0 Flash via Vertex AI
  F13 — Session state management across turns
  F16 — Logging & guardrail callbacks
  F19 — Vertex AI Agent Engine deployment target
  F22 — OpenTelemetry tracing via ADK's enable_tracing flag
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

from orchestrator_agent.callbacks import (
    orchestrator_after_model,
    orchestrator_before_model,
)
from orchestrator_agent.tools import (
    get_agent_status,
    list_available_agents,
)
from shared.config import settings

load_dotenv()

# ── Remote A2A sub-agent references ──────────────────────────────────────────
# Each RemoteA2aAgent fetches the target's Agent Card at runtime to discover
# capabilities (F1 — Agent Card Discovery, F9 — A2A Routing).

weather_agent = RemoteA2aAgent(
    name="weather_agent",
    description=(
        "Handles weather queries for any city. "
        "Use for questions like 'What is the weather in Paris?'"
    ),
    agent_card=f"{settings.WEATHER_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

research_agent = RemoteA2aAgent(
    name="research_agent",
    description=(
        "Performs deep research using Google Search grounding. "
        "Use for open-ended research questions requiring up-to-date information."
    ),
    agent_card=f"{settings.RESEARCH_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

code_agent = RemoteA2aAgent(
    name="code_agent",
    description=(
        "Executes Python code in a sandboxed environment. "
        "Use for code generation, debugging, or running calculations."
    ),
    agent_card=f"{settings.CODE_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

data_agent = RemoteA2aAgent(
    name="data_agent",
    description=(
        "Processes structured data and produces CSV/JSON file Artifacts. "
        "Use for data analysis, CSV generation, and structured output tasks."
    ),
    agent_card=f"{settings.DATA_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

async_agent = RemoteA2aAgent(
    name="async_agent",
    description=(
        "Handles long-running tasks (10+ seconds) with asynchronous push "
        "notifications. Use when the task will take a long time to complete."
    ),
    agent_card=f"{settings.ASYNC_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

# ── Root Orchestrator LLM Agent ───────────────────────────────────────────────

_SYSTEM_INSTRUCTION = """
You are the Orchestrator Agent for the A2A Protocol Demo.

Your role is to route incoming user requests to the most appropriate specialist
agent from your team:

- **weather_agent**: Use for weather queries about any city.
- **research_agent**: Use for open-ended research requiring current information.
- **code_agent**: Use for code generation, execution, or debugging tasks.
- **data_agent**: Use for data processing, CSV generation, or analysis tasks.
- **async_agent**: Use for long-running tasks that do not require an immediate response.

You also have access to local utility tools:
- **list_available_agents**: Lists all specialist agents and their current URLs.
- **get_agent_status**: Checks if a specific agent's server is reachable.

Always be transparent about which agent you are routing to and why.
If a task spans multiple domains, break it into sub-tasks and delegate each.
"""

root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="orchestrator",
    description="Root orchestrator that routes requests to specialist A2A agents.",
    instruction=_SYSTEM_INSTRUCTION,
    sub_agents=[
        weather_agent,
        research_agent,
        code_agent,
        data_agent,
        async_agent,
    ],
    tools=[
        list_available_agents,
        get_agent_status,
    ],
    # Callbacks (F16 — Logging, F17 — Safety)
    before_model_callback=orchestrator_before_model,
    after_model_callback=orchestrator_after_model,
)
