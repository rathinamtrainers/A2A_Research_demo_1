# Speaker Notes — `shared/config.py`

> **File**: `shared/config.py` (137 lines)
> **Purpose**: Centralised configuration loader for the entire A2A Protocol Demo.
> **Estimated teaching time**: 10–15 minutes

---

## Why This File Matters

Start here when teaching the project. Every single agent — weather, research,
code, data, async, orchestrator, pipeline, parallel, loop — imports from this
one file:

```python
from shared.config import settings
```

This is the **single source of truth** for all environment-driven
configuration. If a student asks "where does agent X get its URL / API key /
GCP project?", the answer is always `shared/config.py`.

---

## Section-by-Section Walkthrough

### 1. Imports and `.env` Loading (lines 1–23)

```python
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)
```

**Explain to students:**

- `python-dotenv` reads key-value pairs from a `.env` file and injects them
  into `os.environ`.
- `Path(__file__).parent.parent` resolves to the project root regardless of
  where Python is invoked from. This makes the config work whether you run
  `python -m weather_agent` from the root or from a subdirectory.
- `override=False` is critical: if a variable is already set in the real
  environment (e.g., from a Docker `ENV` or CI secret), the `.env` file will
  **not** overwrite it. This is the standard 12-factor app convention —
  real environment variables always win.

**Teaching moment**: This is the "layered configuration" pattern. In order of
priority: real environment > `.env` file > dataclass defaults.

---

### 2. The `Settings` Dataclass (lines 26–92)

```python
@dataclass
class Settings:
    GOOGLE_CLOUD_PROJECT: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    )
```

**Explain to students:**

- **Why a `dataclass`?** It gives us typed fields, a clean `__repr__`, and the
  ability to instantiate with defaults — without needing a third-party library
  like Pydantic. It's standard library Python, zero extra dependencies.
- **Why `default_factory=lambda: os.environ.get(...)` instead of just
  `default=os.environ.get(...)`?** The `lambda` defers evaluation. With a
  plain `default`, `os.environ.get()` would execute **at class definition
  time** (import time), before `load_dotenv()` has a chance to populate the
  environment. The `lambda` ensures the value is read **at instantiation
  time**, after `.env` has been loaded.

**This is a common interview question**: "When do default values in Python
dataclasses get evaluated?" Great moment to highlight the difference between
`default` (evaluated once at class definition) and `default_factory` (called
each time an instance is created).

---

### 3. Configuration Categories

Walk students through the five groups of settings:

#### 3a. GCP / Vertex AI (lines 30–42)

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_CLOUD_PROJECT` | `""` (empty) | GCP project ID for Vertex AI calls |
| `GOOGLE_CLOUD_LOCATION` | `"us-central1"` | Region for Vertex AI endpoints |
| `GOOGLE_GENAI_USE_VERTEXAI` | `"1"` | Toggle: `"1"` = Vertex AI, `"0"` = AI Studio |
| `VERTEXAI_STAGING_BUCKET` | `""` (empty) | GCS bucket for deployment artifacts |

**Key insight**: `GOOGLE_GENAI_USE_VERTEXAI` acts as a feature flag. When set
to `"0"`, you can develop locally using Google AI Studio (free tier, API key
only) without needing a GCP project. The validation logic respects this — it
only requires `GOOGLE_CLOUD_PROJECT` when Vertex AI is enabled.

#### 3b. Gemini Model (lines 44–47)

```python
GEMINI_MODEL: str = field(
    default_factory=lambda: os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
)
```

- Defaults to `gemini-2.0-flash` — fast, cheap, good enough for demos.
- Students can swap to `gemini-2.0-pro` or `gemini-2.5-flash` by changing one
  environment variable.
- Every agent reads `settings.GEMINI_MODEL` when constructing its LLM agent.

#### 3c. A2A Agent URLs (lines 49–64)

```python
WEATHER_AGENT_URL:  "http://localhost:8001"
RESEARCH_AGENT_URL: "http://localhost:8002"
CODE_AGENT_URL:     "http://localhost:8003"
DATA_AGENT_URL:     "http://localhost:8004"
ASYNC_AGENT_URL:    "http://localhost:8005"
```

**Explain to students:**

- Each agent is a standalone microservice running on its own port.
- In local development, they all run on `localhost` with sequential ports.
- In production (Cloud Run, GKE), you replace these with real service URLs.
- The orchestrator uses these URLs to discover and call remote agents via
  `RemoteA2aAgent(agent_card_url=settings.WEATHER_AGENT_URL + "/.well-known/agent.json")`.

**Teaching moment**: This is classic service discovery in microservices. In
production you might use DNS-based discovery (Kubernetes services) or a
service registry, but for a demo, environment variables are the right level
of complexity.

#### 3d. Webhook Server (lines 66–72)

```python
WEBHOOK_SERVER_URL: "http://localhost:9000"
WEBHOOK_AUTH_TOKEN: "demo-webhook-secret-token"
```

- The async agent uses push notifications (A2A protocol feature F11).
- When a long-running task completes, the agent POSTs a notification to the
  webhook server.
- `WEBHOOK_AUTH_TOKEN` is the shared secret used to compute HMAC signatures on
  webhook payloads.

#### 3e. API Keys and Auth Secrets (lines 74–85)

```python
CODE_AGENT_API_KEY:        "demo-code-agent-key-12345"
RESEARCH_AGENT_JWT_SECRET: "demo-jwt-secret"
OPENWEATHERMAP_API_KEY:    ""
```

- `CODE_AGENT_API_KEY`: The code agent requires an API key in the `X-API-Key`
  header. This is the simplest auth scheme (A2A feature F13).
- `RESEARCH_AGENT_JWT_SECRET`: Used to sign and verify Bearer JWT tokens for
  the research agent (A2A feature F14).
- `OPENWEATHERMAP_API_KEY`: External third-party API key for real weather data.
  Empty by default — the weather agent falls back to mock data when this is
  not set.

**Security note for students**: The defaults are intentionally insecure demo
values. In production, these must be overridden with real secrets via
environment variables or a secrets manager (e.g., Google Secret Manager).

---

### 4. Validation (lines 94–128)

```python
def validate(self) -> None:
    missing: list[str] = []

    if not self.WEBHOOK_AUTH_TOKEN:
        missing.append("WEBHOOK_AUTH_TOKEN")
    if not self.CODE_AGENT_API_KEY:
        missing.append("CODE_AGENT_API_KEY")
    if not self.RESEARCH_AGENT_JWT_SECRET:
        missing.append("RESEARCH_AGENT_JWT_SECRET")

    use_vertexai = self.GOOGLE_GENAI_USE_VERTEXAI not in ("0", "false", "False", "")
    if use_vertexai and not self.GOOGLE_CLOUD_PROJECT:
        missing.append("GOOGLE_CLOUD_PROJECT (...)")

    if missing:
        raise ValueError("Missing required environment variables:\n  - " + ...)
```

**Explain to students:**

- **Fail-fast principle**: If required configuration is missing, the app fails
  immediately at startup with a clear error message — not five minutes later
  in the middle of an API call.
- **Conditional validation**: `GOOGLE_CLOUD_PROJECT` is only required when
  Vertex AI is enabled. This lets developers run locally with AI Studio
  (free) without needing a GCP project.
- **Why check for non-empty?** The defaults for auth secrets are non-empty demo
  values, so they'll pass validation. In a stricter production setup, you'd
  check that they differ from the demo defaults.
- **Accumulates all errors**: Instead of raising on the first missing variable,
  it collects all of them and reports them together. This saves developers
  from the frustrating "fix one, discover another" cycle.

---

### 5. Singleton and Test Guard (lines 131–136)

```python
settings = Settings()

if "pytest" not in sys.modules:
    settings.validate()
```

**Explain to students:**

- `settings = Settings()` — module-level instantiation creates a **singleton**.
  Every `from shared.config import settings` gets the same instance.
- `if "pytest" not in sys.modules` — this is the test guard. During test
  collection, `pytest` imports all modules to discover tests. If `validate()`
  ran during collection, tests would fail unless you had a real `.env` file.
  This guard skips validation when running under pytest.
- Tests that need to verify validation behavior call `settings.validate()`
  explicitly after setting up the environment with mocks/fixtures.

**Common student question**: "Isn't checking `sys.modules` a hack?" Yes, sort
of. Alternatives include lazy validation (validate on first use) or dependency
injection (pass settings explicitly). But for a demo, this is pragmatic and
clear. The important thing is that production code always validates.

---

## Design Patterns to Highlight

1. **12-Factor App Configuration**: Environment variables as the interface
   between the deployment environment and the application code (Factor III).

2. **Singleton Pattern**: One `Settings` instance shared across all modules.
   No need for global variables or dependency injection containers.

3. **Fail-Fast Startup**: Validate all configuration before any business logic
   runs. Surface misconfiguration immediately.

4. **Layered Defaults**: Real env vars > `.env` file > code defaults. Each
   layer can override the one below it.

5. **Separation of Concerns**: Configuration loading is completely separate
   from business logic. Agents don't know where their settings come from.

---

## Discussion Questions for Students

1. **Why not use Pydantic `BaseSettings`?** It would auto-validate types and
   support `.env` out of the box. The answer: fewer dependencies, and this
   demo is about A2A protocol concepts, not configuration libraries. But
   Pydantic `BaseSettings` would be a great choice in production.

2. **What if you need to change a setting at runtime?** The current design
   reads settings once at startup. For runtime changes, you'd need a config
   reload mechanism or a config server (e.g., etcd, Consul).

3. **How would you handle secrets in production?** Use Google Secret Manager,
   AWS Secrets Manager, or HashiCorp Vault. Mount secrets as environment
   variables in Cloud Run / GKE. Never commit secrets to source control.

4. **Why are all values strings?** Environment variables are always strings.
   You could add type coercion (e.g., `int(os.environ.get("PORT", "8080"))`),
   but for this demo, all config values happen to be strings.

---

## Related Files

- `.env.example` — Template showing all variables with placeholder values
- `ENV_SETUP.md` — Setup instructions for students
- `tests/test_config.py` — Tests for defaults, env overrides, and validation
- `shared/auth.py` — Consumes `settings.CODE_AGENT_API_KEY`,
  `settings.RESEARCH_AGENT_JWT_SECRET`, and `settings.WEBHOOK_AUTH_TOKEN`
- Every `agent_name/agent.py` — Consumes `settings.GEMINI_MODEL` and agent URLs
