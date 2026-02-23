"""
Webhook Server — Receives and logs A2A push notification deliveries.

This FastAPI server is the webhook endpoint registered with async_agent
via ``tasks/pushNotificationConfig/set``.  It receives ``TaskStatusUpdateEvent``
and ``TaskArtifactUpdateEvent`` POST requests and logs/stores them.

Demonstrates:
  F4 — Push notification delivery and receipt
  F4 — Webhook authentication (HMAC-SHA256 signature verification)

Usage::

    uvicorn webhook_server.main:app --port 9000
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from rich.console import Console
from rich.panel import Panel

from shared.auth import verify_webhook_signature
from shared.config import settings

console = Console()

app = FastAPI(
    title="A2A Webhook Receiver",
    description="Receives push notification deliveries from A2A agents.",
    version="1.0.0",
)

# ── In-memory event store ─────────────────────────────────────────────────────
# Maps task_id → list of received events (in arrival order)
_event_log: dict[str, list[dict]] = defaultdict(list)

# ── Persistence configuration ─────────────────────────────────────────────────
# Events are written to a JSONL file for replay and audit purposes.
_EVENTS_FILE: Path = Path(
    os.environ.get("WEBHOOK_EVENTS_FILE", "/tmp/webhook_events.jsonl")
)


def _persist_event(event: dict) -> None:
    """
    Append an event to the JSONL persistence file.

    Each line is a self-contained JSON object.  This allows replaying events
    after a server restart.

    Args:
        event: The event dict to persist.
    """
    try:
        with _EVENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass  # Non-fatal — in-memory store remains the source of truth


def _load_persisted_events() -> None:
    """
    Load previously persisted events from the JSONL file on startup.

    This allows the server to resume with historical event data across
    process restarts.
    """
    if not _EVENTS_FILE.exists():
        return
    try:
        with _EVENTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        event = json.loads(line)
                        task_id = event.get("taskId", "unknown")
                        _event_log[task_id].append(event)
                    except json.JSONDecodeError:
                        pass  # Skip malformed lines
    except OSError:
        pass


# Load persisted events at import time (module startup)
_load_persisted_events()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "a2a-webhook-receiver",
        "events_received": sum(len(v) for v in _event_log.values()),
    }


@app.post("/webhook")
async def receive_webhook(request: Request) -> JSONResponse:
    """
    Receive and log a push notification event from an A2A agent (F4).

    Verifies the HMAC-SHA256 signature in the ``X-Webhook-Signature`` header
    before processing the event.  Persists accepted events to a JSONL file.

    Args:
        request: Incoming FastAPI request with JSON body.

    Returns:
        ``{"accepted": true}`` on success.

    Raises:
        HTTPException 401: If signature verification fails.
        HTTPException 400: If the request body is not valid JSON.
    """
    body_bytes = await request.body()

    # Verify HMAC signature if present (optional for local dev)
    sig_header = request.headers.get("X-Webhook-Signature", "")
    if sig_header:
        if not verify_webhook_signature(body_bytes, sig_header):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    try:
        event: dict[str, Any] = json.loads(body_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {exc}",
        ) from exc

    # Store event with receipt timestamp
    task_id = event.get("taskId", "unknown")
    event["_received_at"] = datetime.now(timezone.utc).isoformat()
    _event_log[task_id].append(event)

    # Persist event to JSONL file for replay
    _persist_event(event)

    # Log to console for demo visibility
    _log_event(event)

    return JSONResponse(content={"accepted": True}, status_code=status.HTTP_200_OK)


@app.get("/events")
async def list_all_events() -> dict:
    """
    Return all received push notification events grouped by task ID.

    Returns:
        Dict mapping task_id → list of events.
    """
    return dict(_event_log)


@app.get("/events/{task_id}/latest")
async def get_task_latest_event(task_id: str) -> dict:
    """
    Return only the most recent event received for a specific task.

    Args:
        task_id: The task ID to look up.

    Returns:
        Dict with ``task_id`` and ``event`` (the most recent event dict).

    Raises:
        HTTPException 404: If no events found for the task.
    """
    events = _event_log.get(task_id)
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No events found for task: {task_id}",
        )
    return {"task_id": task_id, "event": events[-1]}


@app.get("/events/{task_id}")
async def get_task_events(task_id: str) -> dict:
    """
    Return all events received for a specific task.

    Args:
        task_id: The task ID to look up.

    Returns:
        Dict with ``task_id`` and ``events`` list.

    Raises:
        HTTPException 404: If no events found for the task.
    """
    events = _event_log.get(task_id)
    if events is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No events found for task: {task_id}",
        )
    return {"task_id": task_id, "events": events}


@app.delete("/events")
async def clear_events() -> dict:
    """Clear all stored events (for testing/reset)."""
    count = sum(len(v) for v in _event_log.values())
    _event_log.clear()
    # Also truncate the persistence file
    try:
        _EVENTS_FILE.write_text("")
    except OSError:
        pass
    return {"cleared": count}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log_event(event: dict) -> None:
    """Pretty-print a received push notification event to the console."""
    task_id = event.get("taskId", "?")
    state = event.get("status", {}).get("state", "?")
    progress = event.get("status", {}).get("progress", "?")
    received_at = event.get("_received_at", "?")

    console.print(
        Panel(
            f"[bold cyan]📨 PUSH NOTIFICATION RECEIVED[/bold cyan]\n"
            f"  Task ID  : {task_id}\n"
            f"  State    : [yellow]{state}[/yellow]\n"
            f"  Progress : {progress}%\n"
            f"  Received : {received_at}",
            title="[dim]webhook_server[/dim]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
