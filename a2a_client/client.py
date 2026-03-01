"""
Standalone A2A HTTP/JSON-RPC Client (no ADK dependency).

Demonstrates F24 — Cross-Framework Interoperability:
  - Fetches Agent Card from ``/.well-known/agent.json``
  - Sends messages via ``message/send`` (JSON-RPC 2.0)
  - Streams responses via ``message/stream`` (SSE)
  - Polls task status via ``tasks/get``

This module uses only the ``a2a-sdk`` package — no ``google-adk``.

Usage::

    python -m a2a_client.client

Or import and use programmatically::

    from a2a_client.client import A2ADemoClient
    client = A2ADemoClient("http://localhost:8001")
    card = await client.fetch_agent_card()
    task = await client.send_message("What is the weather in Paris?")
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator, Optional

import httpx
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

from shared.config import settings

console = Console()


class A2ADemoClient:
    """
    Minimal A2A HTTP client using raw httpx (no ADK, no a2a-sdk A2AClient).

    Implements the JSON-RPC 2.0 message framing required by the A2A protocol.
    Demonstrates that any HTTP client can communicate with A2A-compliant agents.

    Args:
        base_url: Base URL of the A2A agent server, e.g. ``"http://localhost:8001"``.
        api_key: Optional API key sent as ``X-API-Key`` header.
        bearer_token: Optional Bearer token sent as ``Authorization`` header.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["X-API-Key"] = api_key
        if bearer_token:
            self._headers["Authorization"] = f"Bearer {bearer_token}"

    async def fetch_agent_card(self) -> dict:
        """
        Fetch the Agent Card from ``/.well-known/agent.json`` (F1).

        Returns:
            Parsed Agent Card dict.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.base_url}/.well-known/agent.json",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def send_message(
        self, text: str, task_id: Optional[str] = None
    ) -> dict:
        """
        Send a message to the agent and wait for a synchronous response (F2).

        Uses the JSON-RPC 2.0 ``message/send`` method.

        Args:
            text: Plain-text message content.
            task_id: Optional existing task ID to continue a conversation (F6).

        Returns:
            The JSON-RPC result dict containing the Task or Message.
        """
        rpc_id = str(uuid.uuid4())
        message = {
            "messageId": str(uuid.uuid4()),
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
        }
        params: dict = {"message": message}
        if task_id:
            params["taskId"] = task_id

        payload = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "message/send",
            "params": params,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.base_url + "/",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            result = resp.json()

        if "error" in result:
            raise RuntimeError(f"A2A error: {result['error']}")
        return result.get("result", result)

    async def stream_message(self, text: str) -> AsyncIterator[dict]:
        """
        Send a message and stream the response via Server-Sent Events (F3).

        Uses the JSON-RPC 2.0 ``message/stream`` method.

        Args:
            text: Plain-text message content.

        Yields:
            Parsed event dicts (``TaskStatusUpdateEvent``,
            ``TaskArtifactUpdateEvent``, etc.) as they arrive.
        """
        rpc_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "message/stream",
            "params": {
                "message": {
                    "messageId": str(uuid.uuid4()),
                    "role": "user",
                    "parts": [{"kind": "text", "text": text}],
                }
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                self.base_url + "/",
                json=payload,
                headers={**self._headers, "Accept": "text/event-stream"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[len("data:"):].strip()
                        if data_str and data_str != "[DONE]":
                            try:
                                yield json.loads(data_str)
                            except json.JSONDecodeError:
                                pass

    async def get_task(self, task_id: str) -> dict:
        """
        Poll a task's current status (F5 — tasks/get).

        Args:
            task_id: The task ID returned by ``send_message``.

        Returns:
            The Task dict with current status and artifacts.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/get",
            "params": {"id": task_id},
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.base_url + "/",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            result = resp.json()
        if "error" in result:
            raise RuntimeError(f"A2A error: {result['error']}")
        return result.get("result", result)

    async def set_push_notification_config(
        self, task_id: str, webhook_url: str, token: Optional[str] = None
    ) -> dict:
        """
        Register a webhook for push notifications on a task (F4).

        Args:
            task_id: The task ID to monitor.
            webhook_url: URL where the server will POST updates.
            token: Optional Bearer token for webhook authentication.

        Returns:
            Confirmation dict.
        """
        config: dict = {"url": webhook_url}
        if token:
            config["token"] = token

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/pushNotificationConfig/set",
            "params": {
                "taskId": task_id,
                "pushNotificationConfig": config,
            },
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.base_url + "/",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            result = resp.json()
        if "error" in result:
            raise RuntimeError(f"A2A error: {result['error']}")
        return result.get("result", result)


# ── Demo runner ───────────────────────────────────────────────────────────────

async def run_demo() -> None:
    """
    Run the complete A2A client demo against the weather_agent (F24).

    Demonstrates:
    1. Agent Card discovery
    2. Synchronous message/send
    3. SSE streaming
    """
    client = A2ADemoClient(settings.WEATHER_AGENT_URL)

    console.rule("[bold cyan]A2A Client Demo — F24 Cross-Framework Interoperability")

    # Step 1: Fetch Agent Card
    console.print("\n[bold]Step 1: Fetch Agent Card[/bold]")
    try:
        card = await client.fetch_agent_card()
        console.print(Panel(JSON(json.dumps(card, indent=2)), title="Agent Card"))
    except Exception as exc:
        console.print(f"[red]Failed to fetch Agent Card: {exc}[/red]")
        console.print(f"[yellow]Make sure weather_agent is running at {settings.WEATHER_AGENT_URL}[/yellow]")
        return

    # Step 2: Synchronous message/send
    console.print("\n[bold]Step 2: Synchronous message/send[/bold]")
    try:
        result = await client.send_message("What is the weather in London?")
        console.print(Panel(JSON(json.dumps(result, indent=2, default=str)), title="Task Result"))
    except Exception as exc:
        console.print(f"[red]message/send failed: {exc}[/red]")

    # Step 3: SSE streaming
    console.print("\n[bold]Step 3: SSE Streaming (message/stream)[/bold]")
    try:
        async for event in client.stream_message("Give me a 5-day forecast for Paris."):
            console.print(f"  [green]SSE Event:[/green] {json.dumps(event)}")
    except Exception as exc:
        console.print(f"[red]Streaming failed: {exc}[/red]")

    console.rule("[bold cyan]Demo Complete")


if __name__ == "__main__":
    asyncio.run(run_demo())
