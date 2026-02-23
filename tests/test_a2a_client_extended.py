"""
Extended tests for a2a_client/client.py — headers, URL normalisation,
JSON-RPC message structure, and error propagation.

Reference: F24 — Cross-Framework Interoperability; F1, F2, F4, F5.
"""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock


# ── URL normalisation ─────────────────────────────────────────────────────────


class TestUrlNormalization:
    """A2ADemoClient strips trailing slashes from base_url."""

    def test_trailing_slash_is_stripped(self):
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001/")
        assert client.base_url == "http://localhost:8001"

    def test_double_trailing_slash_stripped(self):
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001//")
        assert client.base_url == "http://localhost:8001"

    def test_no_trailing_slash_unchanged(self):
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        assert client.base_url == "http://localhost:8001"

    def test_path_with_no_trailing_slash_unchanged(self):
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001/path")
        assert client.base_url == "http://localhost:8001/path"


# ── Header construction ───────────────────────────────────────────────────────


class TestClientHeaders:
    """A2ADemoClient adds correct auth headers based on constructor args."""

    @pytest.mark.asyncio
    async def test_api_key_header_set_when_provided(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001", api_key="my-api-key")
        await client.send_message("test")
        assert httpx_mock.get_requests()[0].headers.get("X-API-Key") == "my-api-key"

    @pytest.mark.asyncio
    async def test_bearer_token_header_set_when_provided(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001", bearer_token="my-jwt-token")
        await client.send_message("test")
        assert httpx_mock.get_requests()[0].headers.get("Authorization") == "Bearer my-jwt-token"

    @pytest.mark.asyncio
    async def test_both_api_key_and_bearer_token_set(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient(
            "http://localhost:8001", api_key="key-123", bearer_token="token-abc"
        )
        await client.send_message("test")
        req = httpx_mock.get_requests()[0]
        assert req.headers.get("X-API-Key") == "key-123"
        assert req.headers.get("Authorization") == "Bearer token-abc"

    @pytest.mark.asyncio
    async def test_no_api_key_header_when_not_provided(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        await client.send_message("test")
        req = httpx_mock.get_requests()[0]
        assert "X-API-Key" not in req.headers

    @pytest.mark.asyncio
    async def test_content_type_is_application_json(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        await client.send_message("test")
        ct = httpx_mock.get_requests()[0].headers.get("Content-Type", "")
        assert "application/json" in ct


# ── JSON-RPC message structure ────────────────────────────────────────────────


class TestJsonRpcStructure:
    """Requests must follow JSON-RPC 2.0 message framing."""

    @pytest.mark.asyncio
    async def test_send_message_has_correct_version(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").send_message("Hello")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["jsonrpc"] == "2.0"

    @pytest.mark.asyncio
    async def test_send_message_uses_message_send_method(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").send_message("Hello")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["method"] == "message/send"

    @pytest.mark.asyncio
    async def test_send_message_text_included_in_parts(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").send_message("My unique message")
        body = json.loads(httpx_mock.get_requests()[0].content)
        parts = body["params"]["message"]["parts"]
        assert any(p.get("text") == "My unique message" for p in parts)

    @pytest.mark.asyncio
    async def test_send_message_role_is_user(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").send_message("test")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["params"]["message"]["role"] == "user"

    @pytest.mark.asyncio
    async def test_send_message_has_unique_rpc_id(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        """Each call should generate a unique JSON-RPC request ID."""
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "2", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        client = A2ADemoClient("http://localhost:8001")
        await client.send_message("first")
        await client.send_message("second")
        requests = httpx_mock.get_requests()
        id1 = json.loads(requests[0].content)["id"]
        id2 = json.loads(requests[1].content)["id"]
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_get_task_uses_tasks_get_method(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").get_task("task-abc")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["method"] == "tasks/get"
        assert body["params"]["id"] == "task-abc"

    @pytest.mark.asyncio
    async def test_task_continuation_sends_task_id(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").send_message(
            "Follow-up", task_id="existing-task-id"
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["params"]["taskId"] == "existing-task-id"

    @pytest.mark.asyncio
    async def test_send_message_without_task_id_has_no_task_id_param(
        self, httpx_mock: HTTPXMock, sample_task_response
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={"jsonrpc": "2.0", "id": "1", "result": sample_task_response},
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").send_message("New message")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert "taskId" not in body["params"]


# ── Error propagation ─────────────────────────────────────────────────────────


class TestErrorPropagation:
    """A2ADemoClient must raise RuntimeError on A2A JSON-RPC errors."""

    @pytest.mark.asyncio
    async def test_send_message_raises_on_rpc_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "error": {"code": -32603, "message": "Internal error"},
            },
        )
        from a2a_client.client import A2ADemoClient
        with pytest.raises(RuntimeError, match="A2A error"):
            await A2ADemoClient("http://localhost:8001").send_message("test")

    @pytest.mark.asyncio
    async def test_get_task_raises_on_rpc_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "error": {"code": -32001, "message": "Task not found"},
            },
        )
        from a2a_client.client import A2ADemoClient
        with pytest.raises(RuntimeError, match="A2A error"):
            await A2ADemoClient("http://localhost:8001").get_task("missing-id")

    @pytest.mark.asyncio
    async def test_set_push_config_raises_on_rpc_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "error": {"code": -32602, "message": "Invalid params"},
            },
        )
        from a2a_client.client import A2ADemoClient
        with pytest.raises(RuntimeError, match="A2A error"):
            await A2ADemoClient("http://localhost:8001").set_push_notification_config(
                "t1", "http://hook.test"
            )


# ── Push notification config ──────────────────────────────────────────────────


class TestPushNotificationConfig:
    """Tests for set_push_notification_config request structure."""

    @pytest.mark.asyncio
    async def test_push_config_includes_url(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "result": {"taskId": "t1", "pushNotificationConfig": {"url": "http://hook.test"}},
            },
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").set_push_notification_config(
            "t1", "http://hook.test"
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["params"]["pushNotificationConfig"]["url"] == "http://hook.test"

    @pytest.mark.asyncio
    async def test_push_config_includes_token_when_provided(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "result": {
                    "taskId": "t2",
                    "pushNotificationConfig": {"url": "http://hook.test", "token": "mytoken"},
                },
            },
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").set_push_notification_config(
            "t2", "http://hook.test", token="mytoken"
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        config = body["params"]["pushNotificationConfig"]
        assert config["token"] == "mytoken"

    @pytest.mark.asyncio
    async def test_push_config_no_token_key_when_token_not_provided(
        self, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "result": {"taskId": "t3", "pushNotificationConfig": {"url": "http://hook.test"}},
            },
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").set_push_notification_config(
            "t3", "http://hook.test"
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert "token" not in body["params"]["pushNotificationConfig"]

    @pytest.mark.asyncio
    async def test_push_config_uses_correct_method(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="http://localhost:8001/",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "result": {"taskId": "t4", "pushNotificationConfig": {"url": "http://hook"}},
            },
        )
        from a2a_client.client import A2ADemoClient
        await A2ADemoClient("http://localhost:8001").set_push_notification_config(
            "t4", "http://hook"
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["method"] == "tasks/pushNotificationConfig/set"
