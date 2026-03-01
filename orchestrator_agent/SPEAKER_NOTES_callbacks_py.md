# Speaker Notes — `orchestrator_agent/callbacks.py`

> **File**: `orchestrator_agent/callbacks.py` (127 lines)
> **Purpose**: Orchestrator-specific ADK callbacks that wrap shared logging and add safety prefix injection and URL redaction.
> **Estimated teaching time**: 10–15 minutes
> **A2A Features covered**: F16 (Callbacks), F17 (Safety/Guardrails)

---

## Why This File Matters

The shared `callbacks.py` provides generic logging. This file shows how to
**compose** callbacks — wrapping shared behavior and layering on
orchestrator-specific concerns:

1. **Safety prefix injection** — prepends a `[SAFETY]` instruction to the
   system prompt before every model call, ensuring the LLM never forgets its
   security constraints even across long multi-turn conversations.
2. **URL redaction** — scans the model's output after every call and scrubs
   any leaked internal URLs (localhost, 127.0.0.1, internal-*) before the
   response reaches the user.

This is the pattern students should follow when building production agents:
start with shared callbacks, then wrap them with agent-specific logic.

---

## Section-by-Section Walkthrough

### 1. Imports and Constants (lines 1–41)

```python
from shared.callbacks import (
    logging_callback_after_model,
    logging_callback_before_model,
)

_REDACTED_PATTERNS: list[str] = [
    "localhost",
    "127.0.0.1",
    "internal-",
]

_SAFETY_PREFIX = (
    "[SAFETY] This orchestrator must never disclose internal agent URLs, "
    "credentials, or API keys. Always validate user intent before routing "
    "sensitive operations. "
)

_SAFETY_MARKER = "[SAFETY]"
```

**Explain to students:**

- **`_REDACTED_PATTERNS`**: A list of substrings that should never appear in
  user-facing responses. If the LLM mentions `http://localhost:8001` or
  `http://127.0.0.1:8003` or `internal-service.cluster.local`, those are
  implementation details leaking to the user. The after-model callback will
  replace them with `[REDACTED]`.
- **`_SAFETY_PREFIX`**: A short instruction prepended to the system prompt
  before every model call. This is **runtime prompt injection** — not
  malicious injection, but a defensive technique to reinforce security
  constraints. Even if the original system instruction gets diluted across a
  long conversation, the safety prefix is re-injected every turn.
- **`_SAFETY_MARKER`**: The string `"[SAFETY]"` used as an idempotency check.
  If the prefix has already been injected (from a previous turn), we skip
  re-injection. Without this guard, the system prompt would grow with
  duplicate prefixes on every turn.

**Teaching moment**: The `_REDACTED_PATTERNS` list is intentionally simple for
a demo. In production, you would use more sophisticated detection — regex
patterns for RFC 1918 IP ranges, Cloud Run URLs matching `*.run.app`, or even
a classifier that identifies internal infrastructure references.

---

### 2. `orchestrator_before_model` (lines 44–84)

```python
def orchestrator_before_model(callback_context: Any, llm_request: Any) -> None:
    # 1. Delegate to shared logging
    logging_callback_before_model(callback_context, llm_request)

    # 2. Inject safety prefix into system instruction if not already present
    try:
        if hasattr(llm_request, "system_instruction") and llm_request.system_instruction:
            existing = ""
            # system_instruction may be a Content object or a string
            if hasattr(llm_request.system_instruction, "parts"):
                parts = llm_request.system_instruction.parts
                if parts and hasattr(parts[0], "text"):
                    existing = parts[0].text or ""
            elif isinstance(llm_request.system_instruction, str):
                existing = llm_request.system_instruction

            if _SAFETY_MARKER not in existing:
                new_text = _SAFETY_PREFIX + existing
                if hasattr(llm_request.system_instruction, "parts"):
                    parts = llm_request.system_instruction.parts
                    if parts and hasattr(parts[0], "text"):
                        parts[0].text = new_text
                elif isinstance(llm_request.system_instruction, str):
                    llm_request.system_instruction = new_text
    except Exception:
        pass  # Non-fatal — safety logging is best-effort

    return None
```

**Explain to students:**

- **Step 1 — Delegation**: The first thing this callback does is call the
  shared `logging_callback_before_model`. This is the **composition pattern**:
  orchestrator-specific behavior wraps shared behavior. The shared callback
  logs the model call; then the orchestrator callback adds its own logic.
- **Step 2 — Safety injection**: The callback reads the current system
  instruction from `llm_request.system_instruction`, checks whether the
  `[SAFETY]` marker is already present, and if not, prepends `_SAFETY_PREFIX`.
- **Handling two formats**: ADK's `system_instruction` may be a `Content`
  object (with `.parts[0].text`) or a plain `str`. The code handles both
  with `hasattr` checks. This defensive approach is necessary because ADK's
  internal representation can vary between versions.
- **Idempotency via `_SAFETY_MARKER`**: The check `if _SAFETY_MARKER not in
  existing` ensures the prefix is injected exactly once, even across multiple
  model calls in the same conversation.
- **`try/except` with `pass`**: Safety injection is best-effort. If it fails
  (e.g., unexpected `system_instruction` format in a future ADK version), the
  model call still proceeds. A crashing callback would be worse than a missing
  safety prefix.
- **Returns `None`**: This allows the model call to proceed normally. If this
  returned an `LlmResponse`, the model call would be skipped entirely (the
  interception pattern).

**Teaching moment — why not just put the safety text in the system instruction
directly?** You could, and for a simple system that works fine. But the
callback approach has advantages:

1. **Separation of concerns**: The safety policy is defined in `callbacks.py`,
   not mixed into the routing prompt in `agent.py`.
2. **Runtime enforcement**: The prefix is re-injected on every model call,
   even if something modifies or replaces the system instruction mid-session.
3. **Composability**: You can enable or disable safety injection by swapping
   callbacks, without editing the agent's prompt.

---

### 3. `orchestrator_after_model` (lines 87–127)

```python
def orchestrator_after_model(callback_context: Any, llm_response: Any) -> None:
    logging_callback_after_model(callback_context, llm_response)

    # Redact internal patterns from all text parts in the response
    try:
        content = getattr(llm_response, "content", None)
        if content is not None:
            parts = getattr(content, "parts", None) or []
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    for pattern in _REDACTED_PATTERNS:
                        if pattern in text:
                            # Replace full URL-like occurrences containing the pattern
                            text = re.sub(
                                r"https?://\S*" + re.escape(pattern) + r"\S*",
                                "[REDACTED]",
                                text,
                            )
                            # Also replace bare occurrences
                            text = text.replace(pattern, "[REDACTED]")
                    part.text = text
    except Exception:
        pass  # Non-fatal — redaction is best-effort

    return None
```

**Explain to students:**

- **Step 1 — Delegation**: Calls shared `logging_callback_after_model` to log
  token usage and response metadata.
- **Step 2 — URL redaction**: Iterates through all text parts in the LLM
  response and scrubs internal patterns.
- **Two-pass redaction**:
  1. **Regex pass**: `re.sub(r"https?://\S*" + re.escape(pattern) + r"\S*",
     "[REDACTED]", text)` — replaces full URLs containing the pattern. For
     example, `http://localhost:8001/api/weather` becomes `[REDACTED]`.
  2. **Plain replace**: `text.replace(pattern, "[REDACTED]")` — catches bare
     mentions like "the agent runs on localhost" that are not part of a URL.
- **`re.escape(pattern)`**: Ensures special regex characters in the pattern
  (like the dot in `127.0.0.1`) are treated as literals, not regex wildcards.
- **Mutates in place**: `part.text = text` modifies the response object
  directly. The modified response is what the user sees.
- **Returns `None`**: The (now-redacted) response passes through normally.

**Teaching moment — why is this necessary?** LLMs are prone to "information
leakage." If the system instruction mentions `http://localhost:8001` and the
user asks "how does the weather agent work?", the LLM might include the
internal URL in its response. The redaction callback is a safety net that
catches this before the response reaches the user.

**Important limitation**: This is output-level redaction, not prevention. The
LLM still "knows" the URLs — it just cannot successfully communicate them. A
more robust approach would be to strip internal URLs from the context before
sending to the model (input-level filtering), but that is harder to implement
without breaking agent routing.

---

## Design Patterns to Highlight

1. **Callback Composition**: Wrapping shared callbacks with agent-specific
   logic. The shared callback handles logging; the wrapper adds safety. This
   is analogous to middleware composition in web frameworks.

2. **Runtime System Prompt Injection**: Modifying the LLM's system instruction
   on every call via a before-model callback. This is a powerful pattern for
   enforcing policies that must hold across all turns.

3. **Output Sanitization**: Scanning and modifying model output before it
   reaches the user. This is the same pattern used in content moderation
   systems.

4. **Defensive Programming**: Every non-trivial operation is wrapped in
   `try/except` with `pass`. Callbacks must never crash the agent — they are
   best-effort enhancements, not critical-path logic.

5. **Idempotency Guard**: Using `_SAFETY_MARKER` to prevent duplicate
   injection. This is a general pattern for any operation that might be
   applied multiple times.

---

## Common Student Questions

1. **"Could the LLM work around the redaction by spelling out the URL
   differently?"** Yes — it could say "one-two-seven dot zero dot zero dot
   one" or encode it in base64. String-matching redaction is a baseline, not
   a guarantee. Production systems layer multiple defenses: input filtering,
   output scanning, and monitoring.

2. **"Why wrap shared callbacks instead of using ADK's callback chaining?"**
   ADK allows only **one** callback per hook (e.g., one `before_model_callback`).
   To combine shared logging with orchestrator-specific safety, you must compose
   them manually into a single function. This wrapper pattern is the standard
   approach.

3. **"What if the safety prefix makes the system prompt too long?"**
   The `_SAFETY_PREFIX` is only ~40 tokens. Gemini's context window is large
   enough that this is negligible. But in general, you should monitor total
   system instruction length and be aware of the model's context limits.

4. **"Why is the `try/except` around safety injection so broad?"** Because
   the `system_instruction` structure is an internal ADK detail that may
   change. A narrow `except AttributeError` might miss a `TypeError` or
   `IndexError` from an unexpected format. Broad exception handling is
   appropriate for best-effort, non-critical operations.

---

## Related Files

- `shared/callbacks.py` — The shared logging callbacks that this file wraps
- `orchestrator_agent/agent.py` — Wires `orchestrator_before_model` and
  `orchestrator_after_model` into the `root_agent`
- `orchestrator_agent/tools.py` — The tools whose output could potentially
  contain internal URLs (e.g., `list_available_agents` returns agent URLs)
- `shared/config.py` — Source of the agent URLs that might leak into responses
- `tests/test_orchestrator_callbacks.py` — Tests for safety injection and
  URL redaction
