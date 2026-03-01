# Speaker Notes — `tests/conftest.py`

> **File**: `tests/conftest.py` (163 lines)
> **Purpose**: Shared pytest fixtures for the entire A2A Protocol Demo test suite.
> **Estimated teaching time**: 10–15 minutes

---

## Why This File Matters

Every test file in this project depends on `conftest.py`. Pytest automatically
discovers and loads it before running any test in the `tests/` directory. This
file is the **testing infrastructure foundation** — it ensures that:

1. No test accidentally calls real GCP / Vertex AI services.
2. Every test that needs an A2A JSON-RPC payload gets a consistent, valid one.
3. FastAPI agents can be tested via HTTP without spinning up real servers.

If a student asks "how do the tests run without GCP credentials?", the answer
is always `conftest.py`.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–21)

```python
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
```

**Explain to students:**

- `from __future__ import annotations` enables PEP 604 style type hints
  (`str | None`) on all Python 3.9+ versions. This is a good habit for any
  modern Python project.
- `pytest_asyncio` provides async-aware fixture decorators — needed because
  many of our agents use `async def` handlers.
- `FastAPI TestClient` is from Starlette under the hood. It wraps HTTPX and
  lets you call async ASGI apps **synchronously** in tests — no `await`,
  no event loop management.
- `AsyncMock` and `MagicMock` from `unittest.mock` are imported but used
  primarily by individual test files; they are available here for any fixture
  that needs to construct mock objects.

---

### 2. Async Test Configuration (lines 24–29)

```python
@pytest.fixture(scope="session")
def event_loop_policy():
    """Use asyncio's default event loop policy for tests."""
    return asyncio.DefaultEventLoopPolicy()
```

**Explain to students:**

- `scope="session"` means this fixture is created **once** for the entire test
  run, not once per test function. This avoids the overhead of repeatedly
  creating and tearing down event loop policies.
- `DefaultEventLoopPolicy()` is the standard asyncio policy. This fixture
  exists to make the choice **explicit** — and to provide a hook where you
  could swap in `uvloop.EventLoopPolicy()` for faster async tests if needed.
- Without this, `pytest-asyncio` uses its own default, which may vary between
  versions. Pinning it here prevents subtle cross-version breakage.

**Teaching moment**: Session-scoped fixtures are shared across all tests. This
is efficient for read-only configuration but dangerous for mutable state. A
session-scoped database connection, for example, would share state between
tests and cause flaky failures. The event loop policy is safe because it is
stateless.

---

### 3. Environment / GCP Fixtures (lines 32–60)

#### `mock_env_vars` (lines 34–48) — The Safety Net

```python
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Set safe test environment variables.
    Ensures tests don't accidentally hit real GCP services.
    """
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "0")  # Use AI Studio in tests
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "")       # Force mock weather data
    monkeypatch.setenv("CODE_AGENT_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("WEBHOOK_AUTH_TOKEN", "test-webhook-secret")
    monkeypatch.setenv("RESEARCH_AGENT_JWT_SECRET", "test-jwt-secret")
```

**Explain to students:**

- **`autouse=True` is the critical keyword here.** It means this fixture is
  applied to **every single test function** in the suite — automatically,
  without any test needing to request it. No test can "forget" to mock the
  environment.
- **`monkeypatch.setenv()`** temporarily sets environment variables for the
  duration of one test. When the test ends, `monkeypatch` **automatically
  restores** the original values (or removes the variable if it didn't exist
  before). This is why `monkeypatch` is preferred over `os.environ[...] = ...`
  — cleanup is guaranteed even if the test raises an exception.
- **`GOOGLE_GENAI_USE_VERTEXAI = "0"`** — this is the most important line.
  Setting it to `"0"` tells the system to use Google AI Studio mode, which
  prevents any test from accidentally making Vertex AI API calls that would
  incur real GCP costs.
- **`OPENWEATHERMAP_API_KEY = ""`** — an empty string forces the weather
  agent to use its built-in mock data. This means weather-related tests run
  without needing a real API key and produce deterministic results.
- The auth-related variables (`CODE_AGENT_API_KEY`, `WEBHOOK_AUTH_TOKEN`,
  `RESEARCH_AGENT_JWT_SECRET`) are set to obvious test values so that auth
  middleware works correctly in tests without exposing real secrets.

**Teaching moment**: `autouse=True` is a powerful but double-edged pattern. It
is ideal for safety fixtures like this one where you want **universal** coverage.
But overusing `autouse` for complex setup can make tests hard to understand —
readers have to check `conftest.py` to understand what hidden setup is running.
Use `autouse` sparingly, and only for things that truly must apply everywhere.

#### `requires_vertexai` (lines 51–60)

```python
@pytest.fixture
def requires_vertexai() -> None:
    if not os.environ.get("GOOGLE_CLOUD_PROJECT") or \
       not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        pytest.skip("Vertex AI credentials not configured")
```

**Explain to students:**

- This is a **skip marker** fixture. Tests that need real GCP credentials
  request this fixture, and if the credentials are not present, the test is
  skipped (not failed).
- `pytest.skip()` marks the test as "skipped" in the test report — shown as
  `s` in verbose output. This is different from `pytest.xfail()` (expected
  failure) or simply not running the test.
- **Why not just use `@pytest.mark.skipif`?** You could, but a fixture allows
  more complex logic (e.g., checking multiple environment variables with `or`)
  and provides a descriptive skip message.
- Note this checks `os.environ` directly, not the `settings` object. This is
  intentional — it checks the **real** environment, not the monkeypatched test
  environment, because the point is to detect whether the developer has
  configured actual GCP credentials on their machine.

---

### 4. A2A JSON-RPC Payload Fixtures (lines 63–105)

Three fixtures provide valid JSON-RPC 2.0 request payloads for the A2A
protocol methods:

#### `a2a_message_send_payload` (lines 65–78)

```python
@pytest.fixture
def a2a_message_send_payload() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": "test-001",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Hello, test message."}],
            }
        },
    }
```

**Explain to students:**

- This is the **core A2A operation** — sending a message to an agent. The
  structure follows the JSON-RPC 2.0 specification exactly:
  - `"jsonrpc": "2.0"` — protocol version identifier (required by spec).
  - `"id": "test-001"` — request ID for correlating responses.
  - `"method": "message/send"` — the A2A protocol method.
  - `"params"` — method-specific parameters containing the message with
    `role` and `parts`.
- The `parts` array uses `{"kind": "text", "text": "..."}` — this is the
  A2A multimodal content model. Other kinds include `"file"` and `"data"`.

#### `a2a_tasks_get_payload` (lines 81–89)

```python
@pytest.fixture
def a2a_tasks_get_payload() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": "test-002",
        "method": "tasks/get",
        "params": {"id": "test-task-id-001"},
    }
```

- Retrieves a previously created task by ID. Simpler params — just the task ID.

#### `a2a_push_config_set_payload` (lines 92–105)

```python
@pytest.fixture
def a2a_push_config_set_payload() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": "test-003",
        "method": "tasks/pushNotificationConfig/set",
        "params": {
            "taskId": "test-task-id-001",
            "pushNotificationConfig": {
                "url": "http://localhost:9000/webhook",
            },
        },
    }
```

- Configures push notifications for a task — when the task completes, the
  agent POSTs a notification to the specified URL.
- This fixture exercises the async/webhook workflow (A2A feature F11).

**Teaching moment**: By centralizing these payloads as fixtures, every test
that needs to send an A2A request uses the **exact same structure**. This has
two benefits: (1) if the A2A protocol schema changes, you update one place
instead of every test file; (2) you guarantee that tests are using **valid**
payloads — no test is accidentally testing with a malformed request and passing
for the wrong reason.

---

### 5. Sample Response Fixtures (lines 108–146)

#### `sample_task_response` (lines 108–125)

```python
@pytest.fixture
def sample_task_response() -> dict:
    return {
        "id": "test-task-id-001",
        "status": {"state": "completed"},
        "history": [
            {"role": "user",  "parts": [{"kind": "text", "text": "Hello"}]},
            {"role": "agent", "parts": [{"kind": "text", "text": "Hello back!"}]},
        ],
        "artifacts": [],
    }
```

**Explain to students:**

- This represents a **completed** A2A Task. The Task object is the central
  state container in the A2A protocol — it holds:
  - `id` — unique task identifier.
  - `status` — current state (`submitted`, `working`, `completed`, `failed`).
  - `history` — ordered list of messages exchanged between user and agent.
  - `artifacts` — output files/data produced by the agent (empty here).
- Note the `history` contains both `user` and `agent` messages, forming a
  conversation. This is how multi-turn interactions are represented.

#### `sample_agent_card` (lines 128–146)

```python
@pytest.fixture
def sample_agent_card() -> dict:
    return {
        "name": "test_agent",
        "description": "A test agent.",
        "url": "http://localhost:8001",
        "version": "1.0.0",
        "skills": [
            {
                "id": "test_skill",
                "name": "Test Skill",
                "description": "Does a test thing.",
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain"],
            }
        ],
        "capabilities": {"streaming": True, "pushNotifications": False},
    }
```

**Explain to students:**

- The **Agent Card** is how agents advertise themselves in the A2A protocol.
  It is served at `/.well-known/agent.json` and tells other agents (and the
  orchestrator) what this agent can do.
- `skills` — each agent declares its capabilities. `inputModes` and
  `outputModes` specify what content types the skill can handle.
- `capabilities` — protocol-level features. `streaming: True` means the agent
  supports Server-Sent Events (SSE) for real-time responses. `pushNotifications:
  False` means it does not support webhook callbacks.
- This fixture is used by tests that need to validate Agent Card parsing,
  orchestrator agent discovery, or client-side card fetching.

---

### 6. FastAPI TestClient Fixtures (lines 149–162)

```python
@pytest.fixture
def async_agent_client():
    """FastAPI TestClient for async_agent."""
    from async_agent.agent import app
    return TestClient(app)


@pytest.fixture
def webhook_server_client():
    """FastAPI TestClient for webhook_server."""
    from webhook_server.main import app
    return TestClient(app)
```

**Explain to students:**

- `TestClient(app)` wraps a FastAPI/Starlette ASGI application in a
  **synchronous** test client. You call `client.get("/")` or
  `client.post("/endpoint", json={...})` just like `requests` — no `await`,
  no running event loop.
- Under the hood, `TestClient` uses HTTPX and spins up a temporary in-process
  ASGI server. No network port is opened — everything stays in-process.
- **Lazy imports**: Note the `from async_agent.agent import app` is inside the
  fixture function, not at the top of the file. This is intentional — it
  defers the import until a test actually requests this fixture. If the import
  were at module level, `conftest.py` would try to import every agent at test
  collection time, which could fail if optional dependencies are missing.
- Each fixture creates a **fresh** `TestClient` per test (default
  function scope). This ensures no state leaks between tests — each test
  gets its own client with clean state.

**Teaching moment**: FastAPI's `TestClient` is one of the most powerful
features for API testing. It lets you write tests that exercise the full HTTP
stack — routing, middleware, request validation, response serialization — but
run at in-process speed with no network overhead. This is why the tests in
this project are fast despite testing HTTP endpoints.

---

## Design Patterns to Highlight

1. **Test Isolation via `autouse`**: `mock_env_vars` guarantees that every test
   runs in a controlled environment. No test can accidentally make real API
   calls or incur cloud costs. This is the "pit of success" pattern — the safe
   path is the default path.

2. **Fixture Composition**: Pytest fixtures can depend on other fixtures,
   forming a dependency graph. Here, `mock_env_vars` depends on `monkeypatch`
   (a built-in pytest fixture). This composability is what makes pytest's
   fixture system so powerful.

3. **Canonical Test Data**: Payload fixtures (`a2a_message_send_payload`, etc.)
   serve as the **single source of truth** for valid A2A protocol structures.
   All tests share the same payloads, ensuring consistency and making protocol
   changes easy to propagate.

4. **Deferred Imports**: TestClient fixtures use function-level imports to
   avoid import-time side effects and to tolerate missing optional
   dependencies gracefully.

5. **Skip Markers for Integration Tests**: `requires_vertexai` lets the test
   suite degrade gracefully — unit tests always run, integration tests run only
   when credentials are available.

---

## Common Student Questions

1. **"Why `monkeypatch.setenv()` instead of `os.environ[...] = ...`?"**
   `monkeypatch` automatically restores the original environment after each
   test, even if the test raises an exception. Manual `os.environ` manipulation
   requires explicit cleanup in a `try/finally` block, which is error-prone.

2. **"Does `autouse=True` apply to tests in subdirectories?"** Yes. A
   `conftest.py` in `tests/` applies to all tests in `tests/` and any
   subdirectories. Pytest walks up from each test file to find all applicable
   `conftest.py` files, applying fixtures from outermost to innermost.

3. **"Why are the payload fixtures not session-scoped?"** They return plain
   dicts, and a test could mutate a dict (e.g., `payload["id"] = "modified"`).
   If the fixture were session-scoped, that mutation would leak to other tests.
   Function scope (the default) gives each test its own fresh copy.

4. **"Can I add more fixtures here?"** Absolutely. `conftest.py` is the right
   place for any fixture used by two or more test files. Fixtures used by only
   one test file should live in that test file instead.

5. **"Why doesn't `requires_vertexai` use `@pytest.mark.skipif`?"** A fixture
   allows more complex skip logic (multiple conditions, custom messages) and
   is more readable when tests already have a long list of decorators. Both
   approaches are valid.

---

## Related Files

- `shared/config.py` — The `Settings` dataclass whose values `mock_env_vars` overrides
- `tests/test_config.py` — Tests that validate config defaults, env overrides, and validation logic
- `tests/test_async_agent.py` — Uses `async_agent_client` fixture for HTTP endpoint tests
- `tests/test_webhook_server.py` — Uses `webhook_server_client` fixture for webhook endpoint tests
- `tests/test_a2a_client.py` — Uses payload fixtures (`a2a_message_send_payload`, etc.)
- `tests/test_shared_auth.py` — Relies on `mock_env_vars` for auth token/secret values
- `async_agent/agent.py` — The FastAPI app wrapped by `async_agent_client`
- `webhook_server/main.py` — The FastAPI app wrapped by `webhook_server_client`
