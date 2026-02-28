"""
Extended lifecycle tests for async_agent — tasks/list pagination, tasks/cancel,
push notification config validation, and HMAC signature helpers.

Reference: F4, F5 — Task Lifecycle Management & Push Notifications.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from async_agent.agent import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_task_store():
    """Isolate each test by clearing module-level task/webhook/running stores."""
    from async_agent import agent as agent_module
    agent_module._task_store.clear()
    agent_module._webhook_store.clear()
    agent_module._running_tasks.clear()
    yield
    # Cancel any running tasks before clearing
    for task in agent_module._running_tasks.values():
        task.cancel()
    agent_module._task_store.clear()
    agent_module._webhook_store.clear()
    agent_module._running_tasks.clear()


def _send_task(client, msg: str = "Hello") -> str:
    """Helper: create a task and return its ID."""
    payload = {
        "jsonrpc": "2.0",
        "id": "helper-send",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": msg}],
            }
        },
    }
    resp = client.post("/", json=payload)
    return resp.json()["result"]["id"]


# ── tasks/list — cursor-based pagination ──────────────────────────────────────


class TestTasksList:
    """Tests for the tasks/list JSON-RPC method."""

    def _list_tasks(self, client, page_size: int = 20, cursor: str | None = None) -> dict:
        params: dict = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor
        payload = {
            "jsonrpc": "2.0",
            "id": "list",
            "method": "tasks/list",
            "params": params,
        }
        return client.post("/", json=payload).json()["result"]

    def test_empty_list_when_no_tasks_exist(self, client):
        result = self._list_tasks(client)
        assert result["tasks"] == []
        assert result["total_count"] == 0
        assert result["next_cursor"] is None

    def test_lists_created_tasks(self, client):
        _send_task(client, "task 1")
        _send_task(client, "task 2")
        _send_task(client, "task 3")
        result = self._list_tasks(client)
        assert result["total_count"] == 3
        assert len(result["tasks"]) == 3

    def test_each_task_has_id_and_status(self, client):
        _send_task(client)
        result = self._list_tasks(client)
        for task in result["tasks"]:
            assert "id" in task
            assert "status" in task

    def test_page_size_limits_results(self, client):
        for _ in range(5):
            _send_task(client)
        result = self._list_tasks(client, page_size=2)
        assert len(result["tasks"]) == 2

    def test_next_cursor_present_when_more_pages_exist(self, client):
        for _ in range(5):
            _send_task(client)
        result = self._list_tasks(client, page_size=2)
        assert result["next_cursor"] is not None

    def test_next_cursor_none_on_last_page(self, client):
        _send_task(client)
        result = self._list_tasks(client, page_size=10)
        assert result["next_cursor"] is None

    def test_cursor_pagination_returns_non_overlapping_pages(self, client):
        for _ in range(6):
            _send_task(client)

        first = self._list_tasks(client, page_size=3)
        cursor = first["next_cursor"]
        assert cursor is not None

        second = self._list_tasks(client, page_size=3, cursor=cursor)

        first_ids = {t["id"] for t in first["tasks"]}
        second_ids = {t["id"] for t in second["tasks"]}
        assert first_ids.isdisjoint(second_ids), "Pages must not overlap"

    def test_cursor_pagination_covers_all_tasks(self, client):
        for _ in range(6):
            _send_task(client)

        all_ids: set[str] = set()
        cursor = None
        while True:
            result = self._list_tasks(client, page_size=2, cursor=cursor)
            for t in result["tasks"]:
                all_ids.add(t["id"])
            cursor = result["next_cursor"]
            if cursor is None:
                break

        assert len(all_ids) == 6

    def test_page_size_clamped_to_max_100(self, client):
        for _ in range(5):
            _send_task(client)
        # page_size=9999 should be clamped — we still get all 5 tasks
        result = self._list_tasks(client, page_size=9999)
        assert len(result["tasks"]) == 5

    def test_page_size_clamped_to_min_1(self, client):
        _send_task(client)
        _send_task(client)
        result = self._list_tasks(client, page_size=0)
        # page_size=0 clamped to 1 → return exactly 1 task
        assert len(result["tasks"]) == 1

    def test_total_count_is_global_not_page_count(self, client):
        for _ in range(5):
            _send_task(client)
        result = self._list_tasks(client, page_size=2)
        assert result["total_count"] == 5  # all tasks, not just this page


# ── tasks/cancel ──────────────────────────────────────────────────────────────


class TestTasksCancel:
    """Tests for the tasks/cancel JSON-RPC method."""

    def _cancel_task(self, client, task_id: str) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": "cancel",
            "method": "tasks/cancel",
            "params": {"id": task_id},
        }
        return client.post("/", json=payload).json()

    def test_cancel_existing_task_returns_canceled_state(self, client):
        task_id = _send_task(client)
        body = self._cancel_task(client, task_id)
        assert "result" in body
        assert body["result"]["status"]["state"] == "canceled"

    def test_cancel_updates_task_in_store(self, client):
        from async_agent import agent as agent_module
        task_id = _send_task(client)
        self._cancel_task(client, task_id)
        assert agent_module._task_store[task_id]["status"]["state"] == "canceled"

    def test_cancel_preserves_task_id(self, client):
        task_id = _send_task(client)
        body = self._cancel_task(client, task_id)
        assert body["result"]["id"] == task_id

    def test_cancel_nonexistent_task_returns_error(self, client):
        body = self._cancel_task(client, "nonexistent-task-999")
        assert "error" in body

    def test_get_after_cancel_reflects_canceled_state(self, client):
        task_id = _send_task(client)
        self._cancel_task(client, task_id)

        get_payload = {
            "jsonrpc": "2.0",
            "id": "get",
            "method": "tasks/get",
            "params": {"id": task_id},
        }
        result = client.post("/", json=get_payload).json()["result"]
        assert result["status"]["state"] == "canceled"


# ── HMAC signature helpers ────────────────────────────────────────────────────


class TestHmacWebhookSignature:
    """Tests for _compute_webhook_signature (the outgoing delivery signature)."""

    def test_signature_has_sha256_prefix(self, monkeypatch):
        import async_agent.agent as agent_module
        monkeypatch.setattr(agent_module.settings, "WEBHOOK_AUTH_TOKEN", "test-secret")
        from async_agent.agent import _compute_webhook_signature
        sig = _compute_webhook_signature(b'{"event":"test"}')
        assert sig.startswith("sha256=")

    def test_signature_hex_length_is_64_chars(self, monkeypatch):
        import async_agent.agent as agent_module
        monkeypatch.setattr(agent_module.settings, "WEBHOOK_AUTH_TOKEN", "test-secret")
        from async_agent.agent import _compute_webhook_signature
        sig = _compute_webhook_signature(b"payload")
        # "sha256=" prefix (7 chars) + 64 hex chars
        assert len(sig) == 7 + 64

    def test_same_body_produces_consistent_signature(self, monkeypatch):
        import async_agent.agent as agent_module
        monkeypatch.setattr(agent_module.settings, "WEBHOOK_AUTH_TOKEN", "test-secret")
        from async_agent.agent import _compute_webhook_signature
        body = b'{"taskId":"task-123"}'
        assert _compute_webhook_signature(body) == _compute_webhook_signature(body)

    def test_different_bodies_produce_different_signatures(self, monkeypatch):
        import async_agent.agent as agent_module
        monkeypatch.setattr(agent_module.settings, "WEBHOOK_AUTH_TOKEN", "secret")
        from async_agent.agent import _compute_webhook_signature
        sig1 = _compute_webhook_signature(b'{"event":"A"}')
        sig2 = _compute_webhook_signature(b'{"event":"B"}')
        assert sig1 != sig2

    def test_signature_verifiable_by_shared_auth(self, monkeypatch):
        """The signature produced by _compute_webhook_signature must pass
        verify_webhook_signature from shared.auth."""
        import async_agent.agent as agent_module
        import shared.auth as auth_module
        secret = "verifiable-secret"
        monkeypatch.setattr(agent_module.settings, "WEBHOOK_AUTH_TOKEN", secret)
        monkeypatch.setattr(auth_module.settings, "WEBHOOK_AUTH_TOKEN", secret)

        from async_agent.agent import _compute_webhook_signature
        from shared.auth import verify_webhook_signature

        body = b'{"taskId":"abc","status":{"state":"completed"}}'
        sig = _compute_webhook_signature(body)
        assert verify_webhook_signature(body, sig) is True


# ── Push notification config validation ───────────────────────────────────────


class TestPushNotificationConfigValidation:
    """Edge cases in push notification config set/get."""

    def test_set_config_requires_url_field(self, client):
        task_id = _send_task(client)
        payload = {
            "jsonrpc": "2.0",
            "id": "pv1",
            "method": "tasks/pushNotificationConfig/set",
            "params": {
                "taskId": task_id,
                "pushNotificationConfig": {},  # missing url
            },
        }
        body = client.post("/", json=payload).json()
        assert "error" in body

    def test_set_config_requires_task_id(self, client):
        payload = {
            "jsonrpc": "2.0",
            "id": "pv2",
            "method": "tasks/pushNotificationConfig/set",
            "params": {
                "pushNotificationConfig": {"url": "http://hook.test"},
                # no taskId
            },
        }
        body = client.post("/", json=payload).json()
        assert "error" in body

    def test_get_config_returns_empty_dict_when_not_set(self, client):
        task_id = _send_task(client)
        payload = {
            "jsonrpc": "2.0",
            "id": "pv3",
            "method": "tasks/pushNotificationConfig/get",
            "params": {"taskId": task_id},
        }
        result = client.post("/", json=payload).json()["result"]
        assert result["pushNotificationConfig"] == {}

    def test_set_then_get_config_roundtrip(self, client):
        task_id = _send_task(client)
        webhook_url = "http://mywebhook.example.com/events"

        # Set
        client.post("/", json={
            "jsonrpc": "2.0", "id": "s",
            "method": "tasks/pushNotificationConfig/set",
            "params": {"taskId": task_id, "pushNotificationConfig": {"url": webhook_url}},
        })

        # Get
        result = client.post("/", json={
            "jsonrpc": "2.0", "id": "g",
            "method": "tasks/pushNotificationConfig/get",
            "params": {"taskId": task_id},
        }).json()["result"]

        assert result["pushNotificationConfig"]["url"] == webhook_url

    def test_set_config_returns_task_id_and_config(self, client):
        task_id = _send_task(client)
        result = client.post("/", json={
            "jsonrpc": "2.0", "id": "r",
            "method": "tasks/pushNotificationConfig/set",
            "params": {
                "taskId": task_id,
                "pushNotificationConfig": {"url": "http://hook.test"},
            },
        }).json()["result"]
        assert result["taskId"] == task_id
        assert "pushNotificationConfig" in result
