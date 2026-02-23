"""
Reusable ADK agent callbacks for the A2A Protocol Demo.

Demonstrates all six ADK callback hooks (F16) and shows three patterns:
1. **Logging** — print every model call / tool call for observability.
2. **Guardrails** — block unsafe tool arguments (F17).
3. **Caching** — return cached results for repeated identical tool calls.

Callbacks have specific signatures defined by ADK:
  - before_model_callback(callback_context, llm_request) -> Optional[LlmResponse]
  - after_model_callback(callback_context, llm_response) -> Optional[LlmResponse]
  - before_tool_callback(tool, tool_args, tool_context) -> Optional[dict]
  - after_tool_callback(tool, tool_args, tool_context, tool_response) -> Optional[dict]
  - before_agent_callback(callback_context) -> Optional[types.Content]
  - after_agent_callback(callback_context) -> Optional[types.Content]
"""

from __future__ import annotations

import time
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel

console = Console()

# ── In-memory tool result cache (demo only, not thread-safe) ──────────────────
_tool_cache: dict[str, Any] = {}


# ── Logging callbacks ─────────────────────────────────────────────────────────

def logging_callback_before_model(callback_context: Any, llm_request: Any) -> None:
    """
    Log each LLM invocation before it is sent to the model.

    Prints the agent name, turn number, and message count so developers
    can track the model call sequence during demos.

    Args:
        callback_context: ADK ``CallbackContext`` with agent metadata.
        llm_request: The ``LlmRequest`` about to be sent.

    Returns:
        ``None`` to let the normal model call proceed.
    """
    # TODO: Replace console.print with structured logging / Cloud Logging
    agent_name = getattr(callback_context, "agent_name", "unknown")
    console.print(
        Panel(
            f"[bold cyan]→ MODEL CALL[/bold cyan]\n"
            f"  Agent : {agent_name}\n"
            f"  Messages: {len(getattr(llm_request, 'contents', []))}",
            title="[dim]before_model_callback[/dim]",
            border_style="dim",
        )
    )
    return None  # pass-through


def logging_callback_after_model(callback_context: Any, llm_response: Any) -> None:
    """
    Log each LLM response after it is received from the model.

    Extracts and logs token usage from the LLM response metadata when
    available (input tokens, output tokens, total).

    Args:
        callback_context: ADK ``CallbackContext``.
        llm_response: The ``LlmResponse`` just received.

    Returns:
        ``None`` to pass the response through unchanged.
    """
    agent_name = getattr(callback_context, "agent_name", "unknown")

    # Extract token usage metadata from the LLM response
    token_info = ""
    try:
        usage = getattr(llm_response, "usage_metadata", None)
        if usage is not None:
            prompt_tokens = getattr(usage, "prompt_token_count", None)
            candidates_tokens = getattr(usage, "candidates_token_count", None)
            total_tokens = getattr(usage, "total_token_count", None)
            if total_tokens is not None:
                token_info = (
                    f" | tokens: prompt={prompt_tokens}, "
                    f"candidates={candidates_tokens}, "
                    f"total={total_tokens}"
                )
    except Exception:
        pass  # Non-fatal — token logging is best-effort

    console.print(
        f"[dim]← after_model_callback[/dim] agent={agent_name}{token_info}"
    )
    return None


def logging_callback_before_tool(
    tool: Any, tool_args: dict, tool_context: Any
) -> None:
    """
    Log every tool invocation before execution.

    Args:
        tool: The ADK ``BaseTool`` being called.
        tool_args: The arguments the LLM provided.
        tool_context: ADK ``ToolContext`` for state access.

    Returns:
        ``None`` to allow the tool call to proceed.
    """
    tool_name = getattr(tool, "name", str(tool))
    console.print(
        f"[bold yellow]⚙  TOOL CALL[/bold yellow] [{tool_name}] args={tool_args}"
    )
    return None


def logging_callback_after_tool(
    tool: Any, tool_args: dict, tool_context: Any, tool_response: dict
) -> None:
    """
    Log every tool result after execution.

    Args:
        tool: The ADK ``BaseTool`` that was called.
        tool_args: The arguments that were passed.
        tool_context: ADK ``ToolContext``.
        tool_response: The dict returned by the tool function.

    Returns:
        ``None`` to pass the response through unchanged.
    """
    tool_name = getattr(tool, "name", str(tool))
    console.print(
        f"[dim]✓ after_tool_callback[/dim] [{tool_name}] "
        f"response_keys={list(tool_response.keys()) if isinstance(tool_response, dict) else '?'}"
    )
    return None


# ── Guardrail callback ────────────────────────────────────────────────────────

# Patterns considered dangerous in code execution contexts (F17)
_DANGEROUS_PATTERNS: list[str] = [
    "os.system",
    "subprocess",
    "shutil.rmtree",
    "__import__",
    "exec(",
    "eval(",
    "open(",
]


def guardrail_callback_before_tool(
    tool: Any, tool_args: dict, tool_context: Any
) -> Optional[dict]:
    """
    Block tool calls that contain dangerous code patterns (F17 — Safety).

    Inspects the ``code`` argument of any tool.  If it contains patterns
    from ``_DANGEROUS_PATTERNS``, the call is blocked and an error dict
    is returned instead of executing the tool.

    Args:
        tool: The ADK ``BaseTool`` being called.
        tool_args: Arguments provided by the LLM.
        tool_context: ADK ``ToolContext``.

    Returns:
        An error dict if the call should be blocked, else ``None`` to
        allow normal execution.
    """
    code_arg: str = tool_args.get("code", "")
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in code_arg:
            console.print(
                f"[bold red]🛡  GUARDRAIL BLOCKED[/bold red] "
                f"tool={getattr(tool, 'name', '?')} pattern='{pattern}'"
            )
            return {
                "error": f"Execution blocked by safety guardrail: '{pattern}' is not allowed."
            }
    return None  # allow


# ── Cache callback ────────────────────────────────────────────────────────────

def cache_callback_before_tool(
    tool: Any, tool_args: dict, tool_context: Any
) -> Optional[dict]:
    """
    Return a cached result for repeated identical tool calls (F16 — Cache).

    Uses a simple in-memory dict keyed by ``(tool_name, frozenset(args))``.
    This is intentionally naive — replace with Redis or Cloud Memorystore
    in production.

    Args:
        tool: The ADK ``BaseTool`` being called.
        tool_args: Arguments provided by the LLM.
        tool_context: ADK ``ToolContext``.

    Returns:
        Cached result dict if available, else ``None`` to execute normally.
    """
    tool_name = getattr(tool, "name", str(tool))
    try:
        cache_key = f"{tool_name}:{sorted(tool_args.items())}"
    except TypeError:
        return None  # non-hashable args, skip cache

    if cache_key in _tool_cache:
        console.print(
            f"[bold green]⚡ CACHE HIT[/bold green] [{tool_name}]"
        )
        return _tool_cache[cache_key]

    return None  # cache miss — execute tool normally


def cache_callback_after_tool(
    tool: Any, tool_args: dict, tool_context: Any, tool_response: dict
) -> None:
    """
    Store a tool result in the cache after execution.

    Args:
        tool: The ADK ``BaseTool`` that executed.
        tool_args: Arguments that were passed.
        tool_context: ADK ``ToolContext``.
        tool_response: The result dict to cache.

    Returns:
        ``None`` (result is stored in the module-level cache as a side effect).
    """
    tool_name = getattr(tool, "name", str(tool))
    try:
        cache_key = f"{tool_name}:{sorted(tool_args.items())}"
        _tool_cache[cache_key] = tool_response
    except TypeError:
        pass  # non-hashable args, skip caching
    return None
