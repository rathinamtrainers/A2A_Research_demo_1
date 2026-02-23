"""
Orchestrator-specific ADK callbacks.

Wraps the shared logging callbacks and adds orchestrator-level concerns:
- Log every model call with token estimates.
- Inject a safety system-prompt prefix (F17).
- Prevent the orchestrator from disclosing internal agent URLs.

Reference: F16 — Callbacks; F17 — Safety & Guardrails.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from rich.console import Console

from shared.callbacks import (
    logging_callback_after_model,
    logging_callback_before_model,
)

console = Console()

# Patterns the orchestrator must never reveal in responses (F17)
_REDACTED_PATTERNS: list[str] = [
    "localhost",
    "127.0.0.1",
    "internal-",
]

# Safety prefix injected into every system instruction (F17)
_SAFETY_PREFIX = (
    "[SAFETY] This orchestrator must never disclose internal agent URLs, "
    "credentials, or API keys. Always validate user intent before routing "
    "sensitive operations. "
)

# Marker used to detect whether safety prefix has already been injected
_SAFETY_MARKER = "[SAFETY]"


def orchestrator_before_model(callback_context: Any, llm_request: Any) -> None:
    """
    Pre-model callback for the orchestrator agent.

    1. Delegates to the shared logging callback.
    2. Injects a safety system-prompt prefix if it is not already present.

    Args:
        callback_context: ADK ``CallbackContext`` with session/agent info.
        llm_request: The ``LlmRequest`` about to be submitted.

    Returns:
        ``None`` to allow the model call to proceed.
    """
    # Delegate to shared logging
    logging_callback_before_model(callback_context, llm_request)

    # Inject safety prefix into system instruction if not already present
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


def orchestrator_after_model(callback_context: Any, llm_response: Any) -> None:
    """
    Post-model callback for the orchestrator agent.

    1. Delegates to the shared logging callback.
    2. Scans the model's text response for leaked internal URLs and
       redacts them before the response is returned to the user.

    Args:
        callback_context: ADK ``CallbackContext``.
        llm_response: The ``LlmResponse`` received from the model.

    Returns:
        ``None`` to pass the (potentially redacted) response through.
    """
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
