# Speaker Notes — `shared/__init__.py`

> **File**: `shared/__init__.py` (27 lines)
> **Purpose**: Package initializer that re-exports key symbols for convenient imports.
> **Estimated teaching time**: 3–5 minutes

---

## Why This File Matters

This is a small file, but it teaches an important Python packaging concept:
**re-exporting** symbols to create a clean public API for a package.

---

## Walkthrough

```python
"""Shared utilities for the A2A Protocol Demo project."""

from shared.config import Settings, settings
from shared.auth import verify_api_key, create_bearer_token, verify_bearer_token
from shared.callbacks import (
    logging_callback_before_model,
    logging_callback_after_model,
    logging_callback_before_tool,
    logging_callback_after_tool,
    guardrail_callback_before_tool,
    cache_callback_before_tool,
)

__all__ = [
    "Settings",
    "settings",
    "verify_api_key",
    "create_bearer_token",
    "verify_bearer_token",
    "logging_callback_before_model",
    "logging_callback_after_model",
    "logging_callback_before_tool",
    "logging_callback_after_tool",
    "guardrail_callback_before_tool",
    "cache_callback_before_tool",
]
```

**Explain to students:**

### What `__init__.py` does

- Makes the `shared/` directory a **Python package**. Without this file (in
  older Python versions) or with it, Python treats `shared/` as an importable
  package.
- Code inside runs **once** when any module first imports from `shared`.

### The re-export pattern

Instead of requiring agents to write:

```python
from shared.config import settings
from shared.auth import verify_api_key
from shared.callbacks import guardrail_callback_before_tool
```

They can write:

```python
from shared import settings, verify_api_key, guardrail_callback_before_tool
```

This is a convenience — the `__init__.py` imports everything from the three
submodules and makes them available at the package level.

### The `__all__` list

- Controls what `from shared import *` exports.
- Also serves as **documentation** — it's a quick inventory of the package's
  public API.
- Tools like linters and IDEs use `__all__` to determine what's public vs.
  private.

### What's NOT exported

Notice that some symbols are deliberately omitted:

- `verify_webhook_signature` from `auth.py` — only used by the webhook server,
  not by agents.
- `cache_callback_after_tool` from `callbacks.py` — the after-tool cache
  callback is paired with `cache_callback_before_tool`; agents that use
  caching import it directly.
- `_tool_cache`, `_DANGEROUS_PATTERNS` — private module-level variables
  (prefixed with `_`).

This is intentional API design: export what agents commonly need, leave the
rest accessible but not promoted.

---

## Design Patterns to Highlight

1. **Facade Pattern**: The `__init__.py` acts as a facade — a simplified
   interface to the three underlying modules.

2. **Explicit Public API**: `__all__` makes the public/private boundary clear.
   Python's convention: if it's in `__all__`, it's public. If it starts with
   `_`, it's private. Everything else is in a grey area.

---

## Common Student Questions

1. **"Do I need `__init__.py` in modern Python?"** For namespace packages (PEP 420),
   no. But for regular packages where you want to run initialization code or
   re-export symbols, yes. It's still standard practice.

2. **"Does importing from `shared` run all three modules?"** Yes. The import
   statements in `__init__.py` trigger `config.py`, `auth.py`, and
   `callbacks.py` to execute. This means `settings.validate()` runs as a side
   effect of `import shared` (unless under pytest).

3. **"Why not just import directly from submodules?"** You can. Both styles work.
   The re-export is a convenience for frequently-used symbols. In this project,
   most agents import directly from `shared.config` and `shared.callbacks`
   for clarity.

---

## Related Files

- `shared/config.py` — Exports `Settings`, `settings`
- `shared/auth.py` — Exports `verify_api_key`, `create_bearer_token`, `verify_bearer_token`
- `shared/callbacks.py` — Exports the six callback functions
