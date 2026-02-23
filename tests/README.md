# tests/

Test suite for all A2A Protocol Demo modules.

## Test Files

| File | Tests |
|---|---|
| `conftest.py` | Shared fixtures: env vars, payloads, clients |
| `test_weather_agent.py` | `get_weather`, `get_forecast`, Agent Card config |
| `test_data_agent.py` | `parse_csv_data`, `compute_statistics`, `generate_csv_report` |
| `test_async_agent.py` | Task lifecycle, push config, cancellation, unknown methods |
| `test_webhook_server.py` | Webhook receipt, HMAC verification, event storage |
| `test_a2a_client.py` | HTTP client: Agent Card, message/send, SSE, push config |
| `test_shared_auth.py` | API key, Bearer token, HMAC signature verification |
| `test_shared_callbacks.py` | Guardrail blocking, cache hit/miss |

## Running Tests

```bash
# Activate venv
source .venv/bin/activate

# Run all unit tests:
pytest tests/ -v

# Run only unit tests (fast):
pytest tests/ -m unit -v

# Run with coverage:
pytest tests/ --cov=. --cov-report=html

# Run a specific test file:
pytest tests/test_weather_agent.py -v

# Run integration tests (requires GCP):
pytest tests/ -m integration -v
```

## Test Markers

| Marker | Description |
|---|---|
| `unit` | Pure unit tests, no network or GCP |
| `integration` | Requires real GCP credentials |
| `eval` | ADK evaluation harness tests (slow) |

## Coverage Targets

- `shared/` — 90%+
- `*_agent/tools.py` — 80%+
- `async_agent/agent.py` — 70%+
- `webhook_server/main.py` — 80%+
- `a2a_client/client.py` — 70%+
