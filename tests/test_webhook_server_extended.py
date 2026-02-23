"""
Extended tests for webhook_server — /events/{task_id}/latest endpoint,
event timestamps, health counter, and multi-task grouping.

Reference: F4 — Push Notifications.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from webhook_server.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_events():
    from webhook_server import main as ws
    ws._event_log.clear()
    yield
    ws._event_log.clear()


def _post_event(client, task_id: str, state: str) -> None:
    """Helper to post a simple status update event."""
    client.post("/webhook", json={
        "taskId": task_id,
        "event": "TaskStatusUpdateEvent",
        "status": {"state": state},
    })


# ── /events/{task_id}/latest endpoint ────────────────────────────────────────


class TestLatestEventEndpoint:
    """Tests for GET /events/{task_id}/latest."""

    def test_latest_returns_200_for_known_task(self, client):
        _post_event(client, "t1", "working")
        resp = client.get("/events/t1/latest")
        assert resp.status_code == 200

    def test_latest_returns_most_recent_event(self, client):
        task_id = "t-order"
        for state in ["working", "working", "completed"]:
            _post_event(client, task_id, state)

        resp = client.get(f"/events/{task_id}/latest")
        event = resp.json()["event"]
        assert event["status"]["state"] == "completed"

    def test_latest_returns_404_for_unknown_task(self, client):
        resp = client.get("/events/no-such-task-xyz/latest")
        assert resp.status_code == 404

    def test_latest_response_contains_task_id(self, client):
        _post_event(client, "t-check-id", "working")
        resp = client.get("/events/t-check-id/latest")
        assert resp.json()["task_id"] == "t-check-id"

    def test_latest_after_single_event_returns_that_event(self, client):
        _post_event(client, "t-single", "submitted")
        resp = client.get("/events/t-single/latest")
        assert resp.status_code == 200
        assert resp.json()["event"]["status"]["state"] == "submitted"

    def test_latest_changes_as_new_events_arrive(self, client):
        task_id = "t-progress"
        _post_event(client, task_id, "working")
        assert client.get(f"/events/{task_id}/latest").json()["event"]["status"]["state"] == "working"

        _post_event(client, task_id, "completed")
        assert client.get(f"/events/{task_id}/latest").json()["event"]["status"]["state"] == "completed"


# ── Event timestamps ──────────────────────────────────────────────────────────


class TestEventTimestamps:
    """Events must be stored with an ISO-8601 _received_at timestamp."""

    def test_events_have_received_at_field(self, client):
        _post_event(client, "t-ts", "working")
        events = client.get("/events/t-ts").json()["events"]
        assert "_received_at" in events[0]

    def test_timestamp_is_parseable_as_datetime(self, client):
        _post_event(client, "t-iso", "working")
        ts_str = client.get("/events/t-iso").json()["events"][0]["_received_at"]
        # Should parse without raising
        datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

    def test_timestamp_is_a_string(self, client):
        _post_event(client, "t-str-ts", "completed")
        ts = client.get("/events/t-str-ts").json()["events"][0]["_received_at"]
        assert isinstance(ts, str)

    def test_multiple_events_all_have_timestamps(self, client):
        task_id = "t-multi-ts"
        for state in ["working", "working", "completed"]:
            _post_event(client, task_id, state)
        events = client.get(f"/events/{task_id}").json()["events"]
        for ev in events:
            assert "_received_at" in ev


# ── Health check event counter ────────────────────────────────────────────────


class TestHealthCheckEventCounter:
    """GET / shows the total number of received events."""

    def test_initial_count_is_zero(self, client):
        resp = client.get("/")
        assert resp.json()["events_received"] == 0

    def test_count_increments_after_each_event(self, client):
        _post_event(client, "t1", "working")
        assert client.get("/").json()["events_received"] == 1

        _post_event(client, "t2", "working")
        assert client.get("/").json()["events_received"] == 2

    def test_multiple_events_same_task_all_counted(self, client):
        for state in ["working", "working", "completed"]:
            _post_event(client, "t-same", state)
        assert client.get("/").json()["events_received"] == 3

    def test_clear_resets_counter_to_zero(self, client):
        _post_event(client, "t1", "working")
        _post_event(client, "t2", "working")
        client.delete("/events")
        assert client.get("/").json()["events_received"] == 0

    def test_health_response_has_expected_fields(self, client):
        resp = client.get("/")
        body = resp.json()
        assert "status" in body
        assert "events_received" in body
        assert body["status"] == "ok"


# ── Multi-task event grouping ─────────────────────────────────────────────────


class TestMultiTaskEventGrouping:
    """Events for different tasks are stored independently."""

    def test_events_grouped_by_task_id(self, client):
        _post_event(client, "task-A", "working")
        _post_event(client, "task-B", "working")
        _post_event(client, "task-A", "completed")

        all_events = client.get("/events").json()
        assert "task-A" in all_events
        assert "task-B" in all_events

    def test_each_task_has_correct_event_count(self, client):
        for _ in range(3):
            _post_event(client, "task-X", "working")
        _post_event(client, "task-Y", "completed")

        all_events = client.get("/events").json()
        assert len(all_events["task-X"]) == 3
        assert len(all_events["task-Y"]) == 1

    def test_events_for_different_tasks_do_not_cross_contaminate(self, client):
        _post_event(client, "alpha", "working")
        _post_event(client, "beta", "completed")

        alpha_events = client.get("/events/alpha").json()["events"]
        beta_events = client.get("/events/beta").json()["events"]

        assert all(e["status"]["state"] == "working" for e in alpha_events)
        assert all(e["status"]["state"] == "completed" for e in beta_events)


# ── Webhook with no signature header ─────────────────────────────────────────


class TestOptionalSignatureHeader:
    """The X-Webhook-Signature header is optional for local dev."""

    def test_no_signature_header_is_accepted(self, client):
        """Without any X-Webhook-Signature, events are accepted unconditionally."""
        resp = client.post("/webhook", json={
            "taskId": "t-nosig",
            "status": {"state": "working"},
        })
        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

    def test_event_stored_even_without_signature(self, client):
        client.post("/webhook", json={
            "taskId": "t-stored",
            "status": {"state": "working"},
        })
        resp = client.get("/events/t-stored")
        assert resp.status_code == 200
        assert len(resp.json()["events"]) == 1


# ── Invalid JSON rejection ────────────────────────────────────────────────────


class TestInvalidJsonRejection:
    """Non-JSON request bodies must be rejected with 400."""

    def test_invalid_json_returns_400(self, client):
        resp = client.post(
            "/webhook",
            content=b"this is not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_truncated_json_returns_400(self, client):
        resp = client.post(
            "/webhook",
            content=b'{"taskId": "t1"',  # unclosed brace
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
