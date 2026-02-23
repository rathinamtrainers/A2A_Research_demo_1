"""
Shared pytest fixtures for the A2A Protocol Demo test suite.

Provides:
- AsyncIO event loop configuration
- Mock httpx clients (via pytest-httpx)
- Sample A2A payloads for reuse across tests
- Agent fixtures that skip if environment is not configured
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient


# ── Async test configuration ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use asyncio's default event loop policy for tests."""
    return asyncio.DefaultEventLoopPolicy()


# ── Environment / GCP fixtures ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Set safe test environment variables.

    Ensures tests don't accidentally hit real GCP services
    unless explicitly configured.
    """
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "0")  # Use AI Studio in tests
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "")  # Force mock weather data
    monkeypatch.setenv("CODE_AGENT_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("WEBHOOK_AUTH_TOKEN", "test-webhook-secret")
    monkeypatch.setenv("RESEARCH_AGENT_JWT_SECRET", "test-jwt-secret")


@pytest.fixture
def requires_vertexai() -> None:
    """
    Skip test if Vertex AI credentials are not configured.

    Use this fixture for integration tests that need real GCP access.
    """
    if not os.environ.get("GOOGLE_CLOUD_PROJECT") or \
       not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        pytest.skip("Vertex AI credentials not configured (GOOGLE_APPLICATION_CREDENTIALS)")


# ── A2A JSON-RPC payload fixtures ─────────────────────────────────────────────

@pytest.fixture
def a2a_message_send_payload() -> dict:
    """A valid JSON-RPC 2.0 message/send payload."""
    return {
        "jsonrpc": "2.0",
        "id": "test-001",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Hello, test message."}],
            }
        },
    }


@pytest.fixture
def a2a_tasks_get_payload() -> dict:
    """A valid JSON-RPC 2.0 tasks/get payload."""
    return {
        "jsonrpc": "2.0",
        "id": "test-002",
        "method": "tasks/get",
        "params": {"id": "test-task-id-001"},
    }


@pytest.fixture
def a2a_push_config_set_payload() -> dict:
    """A valid JSON-RPC 2.0 tasks/pushNotificationConfig/set payload."""
    return {
        "jsonrpc": "2.0",
        "id": "test-003",
        "method": "tasks/pushNotificationConfig/set",
        "params": {
            "taskId": "test-task-id-001",
            "pushNotificationConfig": {
                "url": "http://localhost:9000/webhook",
            },
        },
    }


@pytest.fixture
def sample_task_response() -> dict:
    """A sample A2A Task response dict."""
    return {
        "id": "test-task-id-001",
        "status": {"state": "completed"},
        "history": [
            {
                "role": "user",
                "parts": [{"kind": "text", "text": "Hello"}],
            },
            {
                "role": "agent",
                "parts": [{"kind": "text", "text": "Hello back!"}],
            },
        ],
        "artifacts": [],
    }


@pytest.fixture
def sample_agent_card() -> dict:
    """A sample Agent Card dict."""
    return {
        "name": "test_agent",
        "description": "A test agent.",
        "url": "http://localhost:8001",
        "version": "1.0.0",
        "skills": [
            {
                "id": "test_skill",
                "name": "Test Skill",
                "description": "Does a test thing.",
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain"],
            }
        ],
        "capabilities": {"streaming": True, "pushNotifications": False},
    }


# ── FastAPI test clients ───────────────────────────────────────────────────────

@pytest.fixture
def async_agent_client():
    """FastAPI TestClient for async_agent."""
    from async_agent.agent import app
    return TestClient(app)


@pytest.fixture
def webhook_server_client():
    """FastAPI TestClient for webhook_server."""
    from webhook_server.main import app
    return TestClient(app)
