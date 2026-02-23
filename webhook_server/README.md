# webhook_server/

FastAPI server that acts as the webhook receiver for A2A push notification
deliveries. This is the endpoint that `async_agent` POSTs progress updates to.

## Features Demonstrated

| Feature | Description |
|---|---|
| F4 — Push Notifications | Receives `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent` deliveries |
| F4 — Webhook Auth | HMAC-SHA256 signature verification via `X-Webhook-Signature` |

## Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI app with `/webhook` endpoint + event store |

## Running Locally

```bash
uvicorn webhook_server.main:app --port 9000
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/webhook` | Receive push notification events |
| `GET` | `/events` | List all received events |
| `GET` | `/events/{task_id}` | Get events for a specific task |
| `DELETE` | `/events` | Clear all events (for testing) |

## Demo Flow

```bash
# 1. Start webhook server:
uvicorn webhook_server.main:app --port 9000

# 2. Start async_agent:
uvicorn async_agent.agent:app --port 8005

# 3. Register webhook with async_agent:
curl -X POST http://localhost:8005/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tasks/pushNotificationConfig/set",
    "params": {
      "taskId": "my-task",
      "pushNotificationConfig": {"url": "http://localhost:9000/webhook"}
    }
  }'

# 4. Watch events arrive:
curl http://localhost:9000/events | jq
```
