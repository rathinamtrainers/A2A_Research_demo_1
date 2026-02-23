"""
Tests for webhook_server — event receipt, storage, and retrieval.

Reference: F4.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_events():
    """Clear the event log before each test to ensure isolation."""
    from webhook_server import main as ws
    ws._event_log.clear()
    yield
    ws._event_log.clear()


@pytest.fixture
def client():
    from webhook_server.main import app
    return TestClient(app)


class TestHealthCheck:
    def test_health_returns_ok(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestWebhookReceiver:
    """Tests for the /webhook POST endpoint."""

    def test_accepts_valid_event(self, client):
        event = {
            "event": "TaskStatusUpdateEvent",
            "taskId": "task-001",
            "status": {"state": "working", "progress": 25},
        }
        resp = client.post("/webhook", json=event)
        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

    def test_stores_event_by_task_id(self, client):
        event = {
            "event": "TaskStatusUpdateEvent",
            "taskId": "task-store-001",
            "status": {"state": "completed", "progress": 100},
        }
        client.post("/webhook", json=event)
        resp = client.get("/events/task-store-001")
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 1
        assert events[0]["status"]["state"] == "completed"

    def test_multiple_events_same_task(self, client):
        task_id = "task-multi-001"
        for state, progress in [("working", 25), ("working", 50), ("completed", 100)]:
            client.post("/webhook", json={
                "event": "TaskStatusUpdateEvent",
                "taskId": task_id,
                "status": {"state": state, "progress": progress},
            })
        resp = client.get(f"/events/{task_id}")
        assert len(resp.json()["events"]) == 3

    def test_rejects_invalid_hmac_signature(self, client, monkeypatch):
        """A request with an incorrect HMAC signature should be rejected."""
        import shared.auth as auth_mod
        monkeypatch.setattr(auth_mod.settings, "WEBHOOK_AUTH_TOKEN", "real-secret")
        event = {"taskId": "task-sig-001", "status": {"state": "working"}}
        resp = client.post(
            "/webhook",
            json=event,
            headers={"X-Webhook-Signature": "sha256=invalidsig"},
        )
        assert resp.status_code == 401

    def test_accepts_valid_hmac_signature(self, client, monkeypatch):
        """A request with a correct HMAC signature should be accepted."""
        import shared.auth as auth_mod
        secret = "test-webhook-secret"
        monkeypatch.setattr(auth_mod.settings, "WEBHOOK_AUTH_TOKEN", secret)
        body_bytes = json.dumps({"taskId": "task-sig-002", "status": {"state": "completed"}}).encode()
        sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        resp = client.post(
            "/webhook",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": f"sha256={sig}",
            },
        )
        assert resp.status_code == 200

    def test_rejects_invalid_json(self, client):
        resp = client.post(
            "/webhook",
            content=b"this is not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400


class TestEventListing:
    """Tests for the /events endpoints."""

    def test_list_all_events_empty(self, client):
        resp = client.get("/events")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_get_nonexistent_task_events_returns_404(self, client):
        resp = client.get("/events/nonexistent-task")
        assert resp.status_code == 404

    def test_clear_events(self, client):
        client.post("/webhook", json={"taskId": "t1", "status": {"state": "working"}})
        resp = client.delete("/events")
        assert resp.json()["cleared"] == 1
        assert client.get("/events").json() == {}
