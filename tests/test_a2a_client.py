"""
Tests for a2a_client — standalone HTTP and gRPC clients.

Uses pytest-httpx to mock HTTP responses without real servers.

Reference: F24, F1, F2, F3, F4, F5.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from pytest_httpx import HTTPXMock


class TestA2ADemoClientFetchAgentCard:
    """Tests for A2ADemoClient.fetch_agent_card()."""

    @pytest.mark.asyncio
    async def test_fetches_agent_card(self, httpx_mock: HTTPXMock, sample_agent_card):
        httpx_mock.add_response(
            url="http://localhost:8001/.well-known/agent.json",
            json=sample_agent_card,
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        card = await client.fetch_agent_card()
        assert card["name"] == "test_agent"
        assert card["capabilities"]["streaming"] is True

    @pytest.mark.asyncio
    async def test_fetch_raises_on_http_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="http://localhost:8001/.well-known/agent.json",
            status_code=404,
        )
        from a2a_client.client import A2ADemoClient
        import httpx
        client = A2ADemoClient("http://localhost:8001")
        with pytest.raises(httpx.HTTPStatusError):
            await client.fetch_agent_card()


class TestA2ADemoClientSendMessage:
    """Tests for A2ADemoClient.send_message()."""

    @pytest.mark.asyncio
    async def test_sends_message_and_returns_result(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        result = await client.send_message("Weather in Paris?")
        assert result["id"] == "test-task-id-001"
        assert result["status"]["state"] == "completed"

    @pytest.mark.asyncio
    async def test_sends_api_key_header(self, httpx_mock: HTTPXMock, sample_task_response):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001", api_key="my-key")
        await client.send_message("test")
        request = httpx_mock.get_requests()[0]
        assert request.headers.get("X-API-Key") == "my-key"

    @pytest.mark.asyncio
    async def test_raises_on_rpc_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "error": {"code": -32603, "message": "Internal error"}},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        with pytest.raises(RuntimeError, match="A2A error"):
            await client.send_message("test")

    @pytest.mark.asyncio
    async def test_includes_task_id_for_continuation(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        await client.send_message("Follow up", task_id="existing-task-id")
        request = httpx_mock.get_requests()[0]
        body = json.loads(request.content)
        assert body["params"]["taskId"] == "existing-task-id"


class TestA2ADemoClientGetTask:
    """Tests for A2ADemoClient.get_task()."""

    @pytest.mark.asyncio
    async def test_gets_task_by_id(self, httpx_mock: HTTPXMock, sample_task_response):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        task = await client.get_task("test-task-id-001")
        assert task["id"] == "test-task-id-001"


class TestA2ADemoClientPushNotification:
    """Tests for A2ADemoClient.set_push_notification_config()."""

    @pytest.mark.asyncio
    async def test_sets_push_config(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "result": {
                    "taskId": "t1",
                    "pushNotificationConfig": {"url": "http://webhook.example.com"},
                },
            },
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        result = await client.set_push_notification_config(
            "t1", "http://webhook.example.com"
        )
        assert result["taskId"] == "t1"
