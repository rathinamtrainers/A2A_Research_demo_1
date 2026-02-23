"""
Custom function tools for the Orchestrator Agent.

These tools give the orchestrator introspection capabilities:
querying which remote agents are configured and whether they are reachable.

ADK function tools are plain Python functions — ADK auto-generates the
JSON schema from type annotations and docstrings.

Reference: F12 — Function Tools.
"""

from __future__ import annotations

import httpx

from shared.config import settings


def list_available_agents() -> dict:
    """
    Return a summary of all configured remote A2A specialist agents.

    Lists each agent's name, role, and current base URL (from environment).
    Useful for the orchestrator to remind itself about available team members.

    Returns:
        A dict with an ``agents`` list, each entry containing
        ``name``, ``description``, and ``url``.
    """
    return {
        "agents": [
            {
                "name": "weather_agent",
                "description": "Real-time weather lookup for any city",
                "url": settings.WEATHER_AGENT_URL,
            },
            {
                "name": "research_agent",
                "description": "Deep research with Google Search grounding",
                "url": settings.RESEARCH_AGENT_URL,
            },
            {
                "name": "code_agent",
                "description": "Sandboxed Python code execution",
                "url": settings.CODE_AGENT_URL,
            },
            {
                "name": "data_agent",
                "description": "Structured data processing and Artifact generation",
                "url": settings.DATA_AGENT_URL,
            },
            {
                "name": "async_agent",
                "description": "Long-running async tasks with push notifications",
                "url": settings.ASYNC_AGENT_URL,
            },
        ]
    }


def get_agent_status(agent_name: str) -> dict:
    """
    Check whether a named specialist agent's HTTP server is reachable.

    Sends a GET request to the agent's ``/.well-known/agent.json`` endpoint
    and reports whether it responded successfully.

    Args:
        agent_name: One of ``weather_agent``, ``research_agent``,
                    ``code_agent``, ``data_agent``, ``async_agent``.

    Returns:
        A dict with ``agent_name``, ``url``, ``reachable`` (bool),
        and an optional ``error`` message.
    """
    url_map = {
        "weather_agent": settings.WEATHER_AGENT_URL,
        "research_agent": settings.RESEARCH_AGENT_URL,
        "code_agent": settings.CODE_AGENT_URL,
        "data_agent": settings.DATA_AGENT_URL,
        "async_agent": settings.ASYNC_AGENT_URL,
    }

    base_url = url_map.get(agent_name)
    if not base_url:
        return {
            "agent_name": agent_name,
            "url": None,
            "reachable": False,
            "error": f"Unknown agent: '{agent_name}'. "
                     f"Valid names: {list(url_map.keys())}",
        }

    probe_url = f"{base_url}/.well-known/agent.json"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(probe_url)
        return {
            "agent_name": agent_name,
            "url": base_url,
            "reachable": resp.status_code == 200,
            "http_status": resp.status_code,
        }
    except httpx.RequestError as exc:
        return {
            "agent_name": agent_name,
            "url": base_url,
            "reachable": False,
            "error": str(exc),
        }
