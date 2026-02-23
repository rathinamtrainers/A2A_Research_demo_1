"""
A2A gRPC Client — Demonstrates gRPC transport binding (F21).

A2A v0.3 includes pre-compiled gRPC stubs in the ``a2a-sdk`` package
(``a2a.grpc.a2a_pb2`` and ``a2a.grpc.a2a_pb2_grpc``).  This module uses
those stubs to communicate with an A2A gRPC server without any additional
protobuf compilation step.

The a2a-sdk gRPC service exposes:
  - ``SendMessage``         → unary RPC equivalent to ``message/send``
  - ``SendStreamingMessage`` → server-streaming RPC equivalent to ``message/stream``
  - ``GetTask``             → unary RPC for task polling
  - ``CancelTask``          → unary RPC for task cancellation
  - ``GetAgentCard``        → unary RPC for agent discovery

Reference: F21 — gRPC Transport (A2A v0.3).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator, Optional

from rich.console import Console

console = Console()

# ── gRPC / proto imports ──────────────────────────────────────────────────────
# The a2a-sdk ships pre-compiled proto stubs — no grpc_tools.protoc required.

try:
    import grpc
    import grpc.aio
    from a2a.grpc import a2a_pb2, a2a_pb2_grpc
    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False

_DEFAULT_GRPC_HOST = "localhost"
_DEFAULT_GRPC_PORT = 50051


class A2AGrpcClient:
    """
    A2A gRPC client using the a2a-sdk's pre-compiled Protobuf stubs (F21).

    Connects to an A2A gRPC server and provides the same logical operations
    as ``A2ADemoClient`` but over HTTP/2 with Protobuf serialisation.

    Args:
        host: gRPC server hostname.
        port: gRPC server port.
        use_tls: Whether to use TLS (required in production).
    """

    def __init__(
        self,
        host: str = _DEFAULT_GRPC_HOST,
        port: int = _DEFAULT_GRPC_PORT,
        use_tls: bool = False,
    ) -> None:
        if not HAS_GRPC:
            raise ImportError(
                "grpcio and a2a-sdk[grpc] are required. "
                "Run: pip install grpcio a2a-sdk"
            )
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[a2a_pb2_grpc.A2AServiceStub] = None

    async def connect(self) -> None:
        """
        Open the gRPC channel and create the service stub.

        Creates either a secure (TLS) or insecure channel based on
        the ``use_tls`` flag.
        """
        target = f"{self.host}:{self.port}"
        if self.use_tls:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.aio.secure_channel(target, credentials)
        else:
            self._channel = grpc.aio.insecure_channel(target)

        self._stub = a2a_pb2_grpc.A2AServiceStub(self._channel)
        console.print(f"[green]gRPC channel opened to {target}[/green]")

    async def disconnect(self) -> None:
        """Close the gRPC channel and release resources."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
            console.print("[dim]gRPC channel closed[/dim]")

    def _ensure_connected(self) -> None:
        """Raise RuntimeError if the channel is not open."""
        if self._stub is None:
            raise RuntimeError(
                "gRPC channel is not open. Call await client.connect() first."
            )

    async def get_agent_card(self) -> dict:
        """
        Fetch the Agent Card via gRPC ``GetAgentCard`` RPC (F1).

        Returns:
            Dict representation of the AgentCard proto message.

        Raises:
            RuntimeError: If not connected.
            grpc.RpcError: On RPC failure.
        """
        self._ensure_connected()
        request = a2a_pb2.GetAgentCardRequest()
        response = await self._stub.GetAgentCard(request)
        return {
            "name": response.name,
            "description": response.description,
            "url": response.url,
            "version": response.version,
        }

    async def send_message(self, text: str, task_id: Optional[str] = None) -> dict:
        """
        Send a message via gRPC ``SendMessage`` RPC (F21).

        Equivalent to the JSON-RPC ``message/send`` method but using
        Protobuf serialisation over HTTP/2.

        Args:
            text: Plain-text message content.
            task_id: Optional existing task ID to continue a multi-turn
                     conversation (F6).

        Returns:
            Parsed response dict with ``task_id`` and ``status``.

        Raises:
            RuntimeError: If not connected.
            grpc.RpcError: On RPC failure.
        """
        self._ensure_connected()

        # Build the protobuf message
        part = a2a_pb2.Part(text=text)
        message = a2a_pb2.Message(
            message_id=str(uuid.uuid4()),
            role=a2a_pb2.ROLE_USER,
            content=[part],
        )
        if task_id:
            message.task_id = task_id

        request = a2a_pb2.SendMessageRequest(message=message)
        response = await self._stub.SendMessage(request)

        # Extract task from response
        task = response.task if hasattr(response, "task") else response
        return {
            "task_id": getattr(task, "id", None),
            "status": getattr(task.status, "state", None) if hasattr(task, "status") else None,
        }

    async def stream_message(self, text: str) -> AsyncIterator[dict]:
        """
        Stream a message response via gRPC server-side streaming (F21).

        Uses the ``SendStreamingMessage`` RPC which yields multiple
        ``StreamResponse`` messages containing ``TaskStatusUpdateEvent``
        payloads.

        Args:
            text: Plain-text message content.

        Yields:
            Parsed event dicts as they arrive from the server.

        Raises:
            RuntimeError: If not connected.
            grpc.RpcError: On RPC failure.
        """
        self._ensure_connected()

        part = a2a_pb2.Part(text=text)
        message = a2a_pb2.Message(
            message_id=str(uuid.uuid4()),
            role=a2a_pb2.ROLE_USER,
            content=[part],
        )
        request = a2a_pb2.SendMessageRequest(message=message)

        async for stream_response in self._stub.SendStreamingMessage(request):
            # stream_response is a StreamResponse proto
            event_dict: dict = {}
            if hasattr(stream_response, "task_status_update_event"):
                evt = stream_response.task_status_update_event
                event_dict = {
                    "event": "TaskStatusUpdateEvent",
                    "task_id": getattr(evt, "task_id", None),
                    "status": {
                        "state": getattr(
                            getattr(evt, "status", None), "state", None
                        )
                    },
                    "final": getattr(evt, "final", False),
                }
            elif hasattr(stream_response, "task_artifact_update_event"):
                evt = stream_response.task_artifact_update_event
                event_dict = {
                    "event": "TaskArtifactUpdateEvent",
                    "task_id": getattr(evt, "task_id", None),
                }
            else:
                event_dict = {"raw": str(stream_response)}

            yield event_dict

    async def get_task(self, task_id: str) -> dict:
        """
        Poll a task's current status via gRPC ``GetTask`` RPC (F5).

        Args:
            task_id: The task ID to look up.

        Returns:
            Task dict with ``task_id`` and ``status``.

        Raises:
            RuntimeError: If not connected.
            grpc.RpcError: On RPC failure.
        """
        self._ensure_connected()
        request = a2a_pb2.GetTaskRequest(task_id=task_id)
        task = await self._stub.GetTask(request)
        return {
            "task_id": getattr(task, "id", None),
            "status": getattr(task.status, "state", None) if hasattr(task, "status") else None,
        }

    async def cancel_task(self, task_id: str) -> dict:
        """
        Cancel a running task via gRPC ``CancelTask`` RPC (F5).

        Args:
            task_id: The task ID to cancel.

        Returns:
            Updated task dict with the new status.

        Raises:
            RuntimeError: If not connected.
            grpc.RpcError: On RPC failure.
        """
        self._ensure_connected()
        request = a2a_pb2.CancelTaskRequest(task_id=task_id)
        task = await self._stub.CancelTask(request)
        return {
            "task_id": getattr(task, "id", None),
            "status": getattr(task.status, "state", None) if hasattr(task, "status") else None,
        }


# ── Demo runner ───────────────────────────────────────────────────────────────


async def run_grpc_demo() -> None:
    """
    Run the gRPC A2A client demo (F21).

    Connects to a gRPC A2A server, fetches the agent card, and sends a
    test message.  The server must support the A2A gRPC service defined
    in the a2a-sdk proto (``a2a.v1.A2AService``).
    """
    console.rule("[bold cyan]A2A gRPC Client Demo — F21")

    if not HAS_GRPC:
        console.print("[red]grpcio is not installed. Run: pip install grpcio[/red]")
        return

    client = A2AGrpcClient(host=_DEFAULT_GRPC_HOST, port=_DEFAULT_GRPC_PORT, use_tls=False)

    try:
        await client.connect()

        # Step 1: Get Agent Card
        console.print("\n[bold]Step 1: Get Agent Card via gRPC[/bold]")
        try:
            card = await client.get_agent_card()
            console.print(f"  Agent: {card}")
        except Exception as exc:
            console.print(f"  [yellow]GetAgentCard failed (server may not be running): {exc}[/yellow]")

        # Step 2: Send message
        console.print("\n[bold]Step 2: Send message via gRPC[/bold]")
        try:
            result = await client.send_message("What is the weather in London?")
            console.print(f"  Result: {result}")
        except Exception as exc:
            console.print(f"  [yellow]SendMessage failed: {exc}[/yellow]")

        # Step 3: Stream message
        console.print("\n[bold]Step 3: Stream message via gRPC[/bold]")
        try:
            async for event in client.stream_message("Give me a forecast for Paris."):
                console.print(f"  [green]gRPC Event:[/green] {event}")
        except Exception as exc:
            console.print(f"  [yellow]Streaming failed: {exc}[/yellow]")

    finally:
        await client.disconnect()

    console.rule("[bold cyan]gRPC Demo Complete")


if __name__ == "__main__":
    asyncio.run(run_grpc_demo())
