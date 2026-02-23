# shared/

Shared utilities used across all agent modules in the A2A Protocol Demo.

## Files

| File | Purpose |
|---|---|
| `config.py` | Singleton `Settings` dataclass loaded from `.env` |
| `auth.py` | Auth helpers: API key, Bearer/JWT, webhook HMAC signature |
| `callbacks.py` | Reusable ADK callbacks: logging, guardrails, caching |

## Usage

```python
from shared.config import settings
from shared.auth import verify_api_key, verify_bearer_token
from shared.callbacks import logging_callback_before_model, guardrail_callback_before_tool
```

## Design Notes

- `config.py` loads `.env` once at import time via `python-dotenv`.
- `auth.py` provides FastAPI dependency functions so they can be injected
  directly into route handlers with `Depends(verify_api_key)`.
- `callbacks.py` functions follow the exact signatures required by ADK's
  `LlmAgent(before_model_callback=..., before_tool_callback=...)` API.
- All callback functions return `None` (pass-through) unless they need to
  block or modify the call.
