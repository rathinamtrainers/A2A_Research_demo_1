"""
Parallel Agent — Concurrent weather queries for 5 cities via ParallelAgent.

Demonstrates:
  F10 — ParallelAgent: all sub-agents run concurrently (fan-out / fan-in)
  F9  — Each sub-agent delegates to the remote weather_agent via A2A

The ``root_agent`` fans out to 5 city-specific LlmAgent instances
simultaneously, then combines results.

Usage::

    adk run ./parallel_agent/
"""

from __future__ import annotations

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

from shared.config import settings

load_dotenv()

# ── City-specific sub-agents ──────────────────────────────────────────────────
# Each city agent has its OWN RemoteA2aAgent instance — an agent instance can
# only belong to one parent, so we cannot share a single RemoteA2aAgent.

_CITIES = ["London", "Tokyo", "New York", "Sydney", "Paris"]


def _make_city_agent(city: str) -> LlmAgent:
    """Create an LlmAgent (with its own RemoteA2aAgent) for a specific city."""
    city_slug = city.lower().replace(" ", "_")
    # Each city gets its own dedicated RemoteA2aAgent instance
    city_weather_remote = RemoteA2aAgent(
        name=f"weather_agent_{city_slug}",
        description=f"Fetches current weather conditions for {city}.",
        agent_card=f"{settings.WEATHER_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    return LlmAgent(
        model=settings.GEMINI_MODEL,
        name=f"weather_{city_slug}",
        description=f"Fetches weather for {city}.",
        instruction=f"Ask the weather_agent for the current weather in {city}. "
                    f"Return a one-line summary: '{city}: <temp>°C, <conditions>'.",
        sub_agents=[city_weather_remote],
        output_key=f"weather_{city_slug}",
    )


city_agents = [_make_city_agent(city) for city in _CITIES]

# ── Aggregator ────────────────────────────────────────────────────────────────

_AGGREGATOR_INSTRUCTION = """
You have received weather data for 5 cities from the parallel sub-agents.
Summarise the results in a clean table:

| City       | Temperature | Conditions |
|------------|-------------|------------|
| London     | ...         | ...        |
| ...

Then identify the warmest and coldest city.
"""

aggregator_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="weather_aggregator",
    description="Combines parallel weather results into a summary table.",
    instruction=_AGGREGATOR_INSTRUCTION,
)

# ── Parallel + Sequential combination ────────────────────────────────────────
# ParallelAgent runs all city_agents concurrently.
# Their results are stored in session state, then aggregator_agent reads them.

parallel_weather = ParallelAgent(
    name="parallel_weather",
    description="Fetches weather for 5 cities simultaneously.",
    sub_agents=city_agents,
)

# The root agent coordinates the parallel fetch then the aggregation
# Using a SequentialAgent wrapper: parallel_weather → aggregator
root_agent = SequentialAgent(
    name="parallel_agent",
    description=(
        "Fetches weather for 5 cities in parallel, then summarises results. "
        "Demonstrates ParallelAgent fan-out/fan-in pattern."
    ),
    sub_agents=[parallel_weather, aggregator_agent],
)
