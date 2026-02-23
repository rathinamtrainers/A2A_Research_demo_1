# a2a_client/

Standalone A2A client that communicates with ADK-hosted agents **without
using any ADK code**. Demonstrates that the A2A protocol is framework-agnostic.

## Features Demonstrated

| Feature | Description |
|---|---|
| F24 — Cross-Framework Interop | Pure `httpx` + JSON-RPC client, no ADK dependency |
| F1 — Agent Discovery | Fetches Agent Card from `/.well-known/agent.json` |
| F2 — Sync Request | `message/send` via JSON-RPC 2.0 |
| F3 — SSE Streaming | `message/stream` via Server-Sent Events |
| F4 — Push Notifications | `tasks/pushNotificationConfig/set` |
| F5 — Task Management | `tasks/get` polling |
| F21 — gRPC Transport | `grpc_client.py` skeleton for gRPC A2A |

## Files

| File | Purpose |
|---|---|
| `client.py` | `A2ADemoClient` — HTTP/JSON-RPC client + demo runner |
| `grpc_client.py` | `A2AGrpcClient` — gRPC client skeleton (needs proto stubs) |

## Running the Demo

```bash
# Requires weather_agent at http://localhost:8001
adk api_server --a2a --port 8001 ./weather_agent/

# Run the demo:
python -m a2a_client.client
```

## Programmatic Usage

```python
from a2a_client.client import A2ADemoClient
import asyncio

async def main():
    client = A2ADemoClient("http://localhost:8001")
    card = await client.fetch_agent_card()
    print(card["name"])  # → "weather_agent"

    result = await client.send_message("Weather in Tokyo?")
    print(result)

asyncio.run(main())
```
