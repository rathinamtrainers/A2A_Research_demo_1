# code_agent/

Remote A2A agent that executes Python code using Gemini's built-in
`code_execution` tool. Protected by API Key authentication.

## Features Demonstrated

| Feature | Description |
|---|---|
| F8 — API Key Auth | Requires `X-API-Key` header on all requests |
| F12 — Built-in Tools | Gemini-native `code_execution` tool (sandboxed Python) |
| F17 — Safety | Guardrail callback blocks `os.system`, `subprocess`, `eval()` |
| F20 — Cloud Run | Containerised via Dockerfile |

## Files

| File | Purpose |
|---|---|
| `agent.py` | `root_agent` + `app` with API key middleware |
| `Dockerfile` | Cloud Run deployment container |

## Running Locally

```bash
# Start server:
adk api_server --a2a --port 8003 ./code_agent/

# Test with API key:
curl -X POST http://localhost:8003/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-code-agent-key-12345" \
  -d '{"jsonrpc":"2.0","method":"message/send","id":1,"params":{...}}'
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CODE_AGENT_API_KEY` | `demo-code-agent-key-12345` | API key for authentication |
