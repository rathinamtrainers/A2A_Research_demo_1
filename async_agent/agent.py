"""
Async Agent — Long-running tasks with push notification delivery.

This agent simulates tasks that take 10–60 seconds (e.g., batch processing,
report generation) and delivers progress updates to the client via webhook.

Demonstrates:
  F3  — SSE streaming (message/stream endpoint emits TaskStatusUpdateEvents)
  F4  — Push notifications: client registers a webhook; agent POSTs updates
  F5  — Full task lifecycle: submitted → working → completed / canceled
  F5  — Task cancellation
  F5  — tasks/list with cursor-based pagination
  F20 — Cloud Run deployment
  F21 — (Optional) gRPC streaming for same long-running tasks

Architecture note:
  Unlike the other agents, async_agent manages a custom A2A request handler
  so it can control the task state machine and push notification delivery
  independently of ADK's default handler.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from shared.config import settings

load_dotenv()

# ── Agent Card (F1, F4) ───────────────────────────────────────────────────────

_long_task_skill = AgentSkill(
    id="long_running_task",
    name="Long-Running Task",
    description=(
        "Executes a simulated long-running task (10–60 seconds) and "
        "delivers progress updates via webhook push notifications."
    ),
    tags=["async", "long-running", "push-notifications"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

AGENT_CARD = AgentCard(
    name="async_agent",
    description=(
        "Handles long-running background tasks with asynchronous push "
        "notification delivery via webhooks."
    ),
    url=settings.ASYNC_AGENT_URL,
    version="1.0.0",
    skills=[_long_task_skill],
    capabilities=AgentCapabilities(
        streaming=True,           # F3 — SSE also supported
        push_notifications=True,  # F4 — Webhook push enabled
    ),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
)

# ── In-memory task store (replace with Redis/DB for production) ───────────────
# Maps task_id → task state dict
_task_store: dict[str, dict] = {}

# Maps task_id → webhook config dict
_webhook_store: dict[str, dict] = {}

# Maps task_id → asyncio.Task (for cancellation support)
_running_tasks: dict[str, asyncio.Task] = {}

# SSE event queues: task_id → list of asyncio.Queue for connected SSE clients
_sse_queues: dict[str, list[asyncio.Queue]] = {}


# ── FastAPI Application ───────────────────────────────────────────────────────

app = FastAPI(title="async_agent A2A Server")


@app.get("/.well-known/agent.json")
async def get_agent_card() -> dict:
    """Return the Agent Card (F1 — Agent Discovery)."""
    return AGENT_CARD.model_dump(exclude_none=True)


@app.post("/")
async def handle_json_rpc(request: Request) -> JSONResponse:
    """
    Main JSON-RPC 2.0 dispatch endpoint.

    Handles:
    - ``message/send``                          → start/continue a task
    - ``message/stream``                        → start task + SSE streaming (F3)
    - ``tasks/get``                             → poll task status
    - ``tasks/cancel``                          → cancel a running task
    - ``tasks/list``                            → list tasks with pagination (F5)
    - ``tasks/pushNotificationConfig/set``      → register webhook (F4)
    - ``tasks/pushNotificationConfig/get``      → retrieve webhook config (F4)

    Args:
        request: Incoming FastAPI request.

    Returns:
        JSON-RPC 2.0 response dict.
    """
    body = await request.json()
    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    try:
        if method == "message/send":
            result = await _handle_message_send(params)
        elif method == "message/stream":
            # SSE streaming — handled separately, returns StreamingResponse
            return await _handle_message_stream(rpc_id, params)
        elif method == "tasks/get":
            result = _handle_tasks_get(params)
        elif method == "tasks/cancel":
            result = await _handle_tasks_cancel(params)
        elif method == "tasks/list":
            result = _handle_tasks_list(params)
        elif method == "tasks/pushNotificationConfig/set":
            result = _handle_push_config_set(params)
        elif method == "tasks/pushNotificationConfig/get":
            result = _handle_push_config_get(params)
        else:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            )
    except Exception as exc:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32603, "message": str(exc)},
            }
        )

    return JSONResponse(content={"jsonrpc": "2.0", "id": rpc_id, "result": result})


# ── JSON-RPC method handlers ──────────────────────────────────────────────────

async def _handle_message_send(params: dict) -> dict:
    """
    Create a new task and start executing it in the background.

    The task simulates 10–30 seconds of work and sends push notifications
    at 25%, 50%, 75%, and 100% progress to the registered webhook.

    Args:
        params: JSON-RPC params containing the user message.

    Returns:
        A Task dict with ``id`` and initial ``status = "submitted"``.
    """
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "status": {"state": "submitted"},
        "history": [params.get("message", {})],
        "artifacts": [],
    }
    _task_store[task_id] = task

    # Schedule background work and store the asyncio.Task for cancellation support
    _running_tasks[task_id] = asyncio.create_task(_execute_long_task(task_id))

    return task


async def _handle_message_stream(
    rpc_id: Any, params: dict
) -> StreamingResponse:
    """
    Create a task and stream progress events via Server-Sent Events (F3).

    Starts the task in the background, creates a per-request SSE queue,
    and yields ``TaskStatusUpdateEvent`` objects as the task progresses.

    Args:
        rpc_id: JSON-RPC request ID.
        params: JSON-RPC params containing the user message.

    Returns:
        A ``StreamingResponse`` that emits SSE ``data:`` lines.
    """
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "status": {"state": "submitted"},
        "history": [params.get("message", {})],
        "artifacts": [],
    }
    _task_store[task_id] = task

    # Create an SSE queue for this connection
    queue: asyncio.Queue = asyncio.Queue()
    _sse_queues.setdefault(task_id, []).append(queue)

    # Start the background task and store for cancellation support
    _running_tasks[task_id] = asyncio.create_task(_execute_long_task(task_id))

    async def _event_generator():
        """Yield SSE data lines until a terminal event is received."""
        # First, yield the initial task object
        initial_event = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "id": task_id,
                "event": "TaskStatusUpdateEvent",
                "status": {"state": "submitted"},
                "final": False,
            },
        }
        yield f"data: {json.dumps(initial_event)}\n\n"

        terminal_states = {"completed", "failed", "canceled"}
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    # Send keep-alive comment
                    yield ": keepalive\n\n"
                    continue

                yield f"data: {json.dumps(event)}\n\n"

                # Exit once a terminal state is emitted
                state = event.get("result", {}).get("status", {}).get("state", "")
                if state in terminal_states:
                    break
        finally:
            # Cleanup queue registration
            queues = _sse_queues.get(task_id, [])
            if queue in queues:
                queues.remove(queue)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _handle_tasks_get(params: dict) -> dict:
    """
    Return the current state of a task by ID (F5 — Task Lifecycle).

    Args:
        params: Dict with ``id`` (task ID).

    Returns:
        The task dict from the in-memory store.

    Raises:
        HTTPException: 404 if task ID is not found.
    """
    task_id = params.get("id")
    if not task_id or task_id not in _task_store:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return _task_store[task_id]


async def _handle_tasks_cancel(params: dict) -> dict:
    """
    Cancel a running task (F5 — Cancellation).

    Args:
        params: Dict with ``id`` (task ID).

    Returns:
        Updated task dict with ``status = "canceled"``.
    """
    task_id = params.get("id")
    if not task_id or task_id not in _task_store:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Cancel the asyncio task
    if task_id in _running_tasks:
        _running_tasks[task_id].cancel()
        del _running_tasks[task_id]

    _task_store[task_id]["status"] = {"state": "canceled"}
    return _task_store[task_id]


def _handle_tasks_list(params: dict) -> dict:
    """
    List tasks with optional cursor-based pagination (F5).

    Args:
        params: Dict with optional ``cursor`` (exclusive start task_id)
                and ``page_size`` (max results, default 20).

    Returns:
        Dict with ``tasks`` (list of task dicts) and ``next_cursor``
        (ID of the last task returned, for fetching the next page).
    """
    cursor = params.get("cursor")
    page_size = int(params.get("page_size", 20))
    page_size = max(1, min(page_size, 100))  # clamp to [1, 100]

    all_ids = list(_task_store.keys())

    # Find starting position after cursor
    start_idx = 0
    if cursor and cursor in _task_store:
        try:
            start_idx = all_ids.index(cursor) + 1
        except ValueError:
            start_idx = 0

    page = all_ids[start_idx : start_idx + page_size]
    tasks = [_task_store[tid] for tid in page]
    next_cursor = page[-1] if len(page) == page_size else None

    return {
        "tasks": tasks,
        "next_cursor": next_cursor,
        "total_count": len(all_ids),
    }


def _handle_push_config_set(params: dict) -> dict:
    """
    Register a webhook URL for push notifications on a task (F4).

    Args:
        params: Dict with ``taskId`` and ``pushNotificationConfig``
                (containing ``url`` and optionally ``token``).

    Returns:
        Confirmation dict with ``taskId`` and registered config.
    """
    task_id = params.get("taskId")
    config = params.get("pushNotificationConfig", {})
    if not task_id or not config.get("url"):
        raise ValueError("taskId and pushNotificationConfig.url are required")
    _webhook_store[task_id] = config
    return {"taskId": task_id, "pushNotificationConfig": config}


def _handle_push_config_get(params: dict) -> dict:
    """
    Retrieve the current webhook config for a task (F4).

    Args:
        params: Dict with ``taskId``.

    Returns:
        The registered push notification config, or an empty dict.
    """
    task_id = params.get("taskId")
    config = _webhook_store.get(task_id or "", {})
    return {"taskId": task_id, "pushNotificationConfig": config}


# ── HMAC signature helpers ────────────────────────────────────────────────────

def _compute_webhook_signature(body_bytes: bytes) -> str:
    """
    Compute the HMAC-SHA256 signature for a webhook delivery payload.

    The signature is added as ``X-Webhook-Signature: sha256=<hex>`` to
    outgoing webhook requests so recipients can verify the delivery.

    Args:
        body_bytes: The raw JSON payload bytes.

    Returns:
        The ``sha256=<hex>`` signature string.
    """
    sig = hmac.new(
        settings.WEBHOOK_AUTH_TOKEN.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"


# ── Background task execution ─────────────────────────────────────────────────

async def _execute_long_task(task_id: str) -> None:
    """
    Simulate a long-running task with progress push notifications.

    Sleeps in 5-second increments, updates task status, and POSTs
    ``TaskStatusUpdateEvent`` payloads to the registered webhook URL.

    Args:
        task_id: The task ID to execute.
    """
    total_duration = 20  # seconds
    steps = 4
    step_duration = total_duration / steps

    try:
        _task_store[task_id]["status"] = {"state": "working"}
        await _push_notification(task_id, "working", progress=0)
        await _emit_sse_event(task_id, "working", progress=0, final=False)

        for step in range(1, steps + 1):
            await asyncio.sleep(step_duration)
            progress = int((step / steps) * 100)

            if step < steps:
                _task_store[task_id]["status"] = {
                    "state": "working",
                    "message": f"Progress: {progress}%",
                }
                await _push_notification(task_id, "working", progress=progress)
                await _emit_sse_event(task_id, "working", progress=progress, final=False)
            else:
                # Final step — complete
                result_artifact = {
                    "artifactId": str(uuid.uuid4()),
                    "parts": [
                        {
                            "kind": "text",
                            "text": f"Long-running task {task_id} completed successfully.",
                        }
                    ],
                }
                _task_store[task_id]["artifacts"].append(result_artifact)
                _task_store[task_id]["status"] = {"state": "completed"}
                await _push_notification(task_id, "completed", progress=100)
                await _emit_sse_event(task_id, "completed", progress=100, final=True)

    except asyncio.CancelledError:
        _task_store[task_id]["status"] = {"state": "canceled"}
        await _push_notification(task_id, "canceled", progress=-1)
        await _emit_sse_event(task_id, "canceled", progress=-1, final=True)
    except Exception as exc:
        _task_store[task_id]["status"] = {"state": "failed", "message": str(exc)}
        await _push_notification(task_id, "failed", progress=-1)
        await _emit_sse_event(task_id, "failed", progress=-1, final=True)
    finally:
        _running_tasks.pop(task_id, None)


async def _emit_sse_event(
    task_id: str, state: str, progress: int, final: bool
) -> None:
    """
    Broadcast a task status update to all connected SSE clients (F3).

    Args:
        task_id: The task that changed state.
        state: New task state string.
        progress: Progress percentage (0–100), or -1 for terminal states.
        final: Whether this is the last event for this task.
    """
    queues = _sse_queues.get(task_id, [])
    if not queues:
        return

    event = {
        "jsonrpc": "2.0",
        "id": None,
        "result": {
            "id": task_id,
            "event": "TaskStatusUpdateEvent",
            "status": {"state": state, "progress": progress},
            "final": final,
        },
    }
    for q in list(queues):
        await q.put(event)


async def _push_notification(task_id: str, state: str, progress: int) -> None:
    """
    POST a TaskStatusUpdateEvent to the registered webhook URL (F4).

    Implements retry logic with exponential backoff (3 retries, initial
    delay of 1 second doubling each attempt).  Adds an HMAC-SHA256
    signature header for webhook authentication.

    Args:
        task_id: The task that changed state.
        state: New task state string.
        progress: Progress percentage (0–100), or -1 for terminal states.
    """
    config = _webhook_store.get(task_id)
    if not config or not config.get("url"):
        return  # No webhook registered

    payload = {
        "event": "TaskStatusUpdateEvent",
        "taskId": task_id,
        "status": {"state": state, "progress": progress},
    }
    body_bytes = json.dumps(payload).encode()

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": _compute_webhook_signature(body_bytes),
    }
    if config.get("token"):
        headers["Authorization"] = f"Bearer {config['token']}"

    max_retries = 3
    delay = 1.0  # seconds

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    config["url"], content=body_bytes, headers=headers
                )
                response.raise_for_status()
                return  # Success
        except (httpx.RequestError, httpx.HTTPStatusError):
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            # On final attempt, give up silently
