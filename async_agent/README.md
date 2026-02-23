# async_agent/

Long-running A2A agent that demonstrates asynchronous push notification
delivery via webhooks. This agent manages its own JSON-RPC dispatcher
rather than using ADK's default handler, giving full control over the
task state machine.

## Features Demonstrated

| Feature | Description |
|---|---|
| F4 — Push Notifications | Registers webhooks and POSTs `TaskStatusUpdateEvent` updates |
| F5 — Task Lifecycle | Full state machine: submitted → working → completed/failed/canceled |
| F5 — Cancellation | `tasks/cancel` cancels the asyncio background task |
| F20 — Cloud Run | Containerised via Dockerfile |

## Files

| File | Purpose |
|---|---|
| `agent.py` | FastAPI app with custom JSON-RPC dispatcher + background task executor |
| `Dockerfile` | Cloud Run deployment container |

## Running Locally

```bash
uvicorn async_agent.agent:app --port 8005
```

## Demo Flow

```bash
# 1. Register a webhook before starting the task:
curl -X POST http://localhost:8005/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0","id":1,"method":"tasks/pushNotificationConfig/set",
    "params":{"taskId":"task-001","pushNotificationConfig":{"url":"http://localhost:9000/webhook"}}
  }'

# 2. Start a long-running task:
curl -X POST http://localhost:8005/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Run a long task"}]}}}'

# 3. Watch the webhook_server receive progress updates.

# 4. Cancel the task:
curl -X POST http://localhost:8005/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tasks/cancel","params":{"id":"<task_id>"}}'
```
