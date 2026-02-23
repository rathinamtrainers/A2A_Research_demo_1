"""
Tests for async_agent — push notifications, task lifecycle, cancellation.

Reference: F4, F5.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from async_agent.agent import app
    return TestClient(app)


class TestAgentCard:
    """Tests for the async_agent Agent Card endpoint."""

    def test_agent_card_endpoint_returns_200(self, client):
        resp = client.get("/.well-known/agent.json")
        assert resp.status_code == 200

    def test_agent_card_has_push_notifications(self, client):
        card = client.get("/.well-known/agent.json").json()
        assert card["capabilities"]["pushNotifications"] is True

    def test_agent_card_has_streaming(self, client):
        card = client.get("/.well-known/agent.json").json()
        assert card["capabilities"]["streaming"] is True


class TestMessageSend:
    """Tests for message/send creating tasks."""

    def test_message_send_returns_task(self, client, a2a_message_send_payload):
        resp = client.post("/", json=a2a_message_send_payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "result" in body
        task = body["result"]
        assert "id" in task
        assert task["status"]["state"] == "submitted"

    def test_message_send_assigns_unique_task_id(self, client, a2a_message_send_payload):
        resp1 = client.post("/", json={**a2a_message_send_payload, "id": "r1"})
        resp2 = client.post("/", json={**a2a_message_send_payload, "id": "r2"})
        id1 = resp1.json()["result"]["id"]
        id2 = resp2.json()["result"]["id"]
        assert id1 != id2


class TestTasksGet:
    """Tests for tasks/get."""

    def test_get_existing_task(self, client, a2a_message_send_payload):
        # Create a task first
        create_resp = client.post("/", json=a2a_message_send_payload)
        task_id = create_resp.json()["result"]["id"]

        # Now get it
        get_payload = {
            "jsonrpc": "2.0",
            "id": "get-001",
            "method": "tasks/get",
            "params": {"id": task_id},
        }
        resp = client.post("/", json=get_payload)
        assert resp.status_code == 200
        task = resp.json()["result"]
        assert task["id"] == task_id

    def test_get_nonexistent_task_returns_error(self, client):
        payload = {
            "jsonrpc": "2.0",
            "id": "get-err",
            "method": "tasks/get",
            "params": {"id": "nonexistent-task-id"},
        }
        resp = client.post("/", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "error" in body


class TestPushNotificationConfig:
    """Tests for push notification config registration."""

    def test_set_and_get_push_config(self, client, a2a_message_send_payload):
        # Create a task
        task_id = client.post("/", json=a2a_message_send_payload).json()["result"]["id"]

        # Set push config
        set_payload = {
            "jsonrpc": "2.0",
            "id": "pc-001",
            "method": "tasks/pushNotificationConfig/set",
            "params": {
                "taskId": task_id,
                "pushNotificationConfig": {"url": "http://test.example.com/webhook"},
            },
        }
        set_resp = client.post("/", json=set_payload)
        assert set_resp.status_code == 200
        assert "error" not in set_resp.json()

        # Get push config
        get_payload = {
            "jsonrpc": "2.0",
            "id": "pc-002",
            "method": "tasks/pushNotificationConfig/get",
            "params": {"taskId": task_id},
        }
        get_resp = client.post("/", json=get_payload)
        config = get_resp.json()["result"]["pushNotificationConfig"]
        assert config["url"] == "http://test.example.com/webhook"


class TestUnknownMethod:
    """Tests for unknown JSON-RPC methods."""

    def test_unknown_method_returns_error(self, client):
        payload = {
            "jsonrpc": "2.0",
            "id": "unk-001",
            "method": "nonexistent/method",
            "params": {},
        }
        resp = client.post("/", json=payload)
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32601
