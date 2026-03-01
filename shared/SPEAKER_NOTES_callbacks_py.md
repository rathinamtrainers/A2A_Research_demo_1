# Speaker Notes — `shared/callbacks.py`

> **File**: `shared/callbacks.py` (248 lines)
> **Purpose**: Reusable ADK agent callbacks demonstrating logging, guardrails, and caching.
> **Estimated teaching time**: 15–20 minutes
> **A2A Features covered**: F16 (Callbacks), F17 (Safety/Guardrails)

---

## Why This File Matters

Google ADK agents have **six callback hooks** — interception points in the
agent's request/response lifecycle. This file implements seven callback
functions across three categories (logging, guardrails, caching) that any
agent can mix and match.

This is one of the most powerful extensibility features in ADK. Callbacks let
you add cross-cutting concerns (observability, security, performance) without
modifying the agent's core logic.

---

## The ADK Callback Pipeline

Draw this diagram on the whiteboard:

```
User message
  │
  ▼
[before_agent_callback]     ← can intercept/short-circuit
  │
  ▼
[before_model_callback]     ← can modify LLM request or return cached response
  │
  ▼
  LLM (Gemini)
  │
  ▼
[after_model_callback]      ← can modify LLM response
  │
  ▼
[before_tool_callback]      ← can block tool call or return cached result
  │
  ▼
  Tool execution
  │
  ▼
[after_tool_callback]       ← can modify tool result or cache it
  │
  ▼
[after_agent_callback]      ← can modify final response
  │
  ▼
Response to user
```

**Key rule**: Returning `None` from a callback means "pass through — don't
modify anything." Returning a **value** means "intercept — use this instead."

---

## Section-by-Section Walkthrough

### 1. Module Setup (lines 1–29)

```python
from rich.console import Console
from rich.panel import Panel

console = Console()
_tool_cache: dict[str, Any] = {}
```

**Explain to students:**

- **Rich library**: Used for coloured, formatted console output. Makes demo
  output visually clear — you can see model calls in cyan, tool calls in
  yellow, guardrail blocks in red, cache hits in green.
- **`_tool_cache`**: A module-level dictionary used by the cache callbacks.
  It's intentionally simple — a plain dict, not thread-safe, no TTL, no
  eviction. This is demo code; production would use Redis or Memorystore.

---

### 2. Logging Callbacks (lines 32–142)

Four callbacks that provide full observability into the agent pipeline:

#### `logging_callback_before_model` (lines 34–59)

```python
def logging_callback_before_model(callback_context, llm_request) -> None:
    agent_name = getattr(callback_context, "agent_name", "unknown")
    console.print(Panel(f"→ MODEL CALL\n  Agent: {agent_name}\n  Messages: {count}"))
    return None  # pass-through
```

**Key points:**
- Fires **before every LLM call**. In a multi-turn conversation, this fires
  multiple times.
- Uses `getattr(..., "unknown")` defensively — the callback context structure
  can vary between ADK versions.
- Returns `None` — this is a pure observer, it doesn't modify anything.

#### `logging_callback_after_model` (lines 62–98)

```python
def logging_callback_after_model(callback_context, llm_response) -> None:
    usage = getattr(llm_response, "usage_metadata", None)
    # Extract prompt_token_count, candidates_token_count, total_token_count
    return None
```

**Key points:**
- Logs **token usage** — critical for cost monitoring.
- The `try/except` with `pass` is intentional: token logging is best-effort.
  Different model versions may structure metadata differently; we don't want
  a logging callback to crash the agent.

**Teaching moment**: In production, you'd send these metrics to Cloud
Monitoring or Prometheus instead of printing to console. The callback pattern
is the same — just swap `console.print()` for a metrics client.

#### `logging_callback_before_tool` (lines 101–119)

```python
def logging_callback_before_tool(tool, args, tool_context) -> None:
    tool_name = getattr(tool, "name", str(tool))
    console.print(f"⚙  TOOL CALL [{tool_name}] args={args}")
    return None
```

**Key points:**
- Note the different **function signature**: tool callbacks receive `tool`,
  `args`, `tool_context` — different from model callbacks which receive
  `callback_context`, `llm_request/response`.
- **Important**: ADK 1.25.1 calls these callbacks with **keyword arguments**:
  `callback(tool=tool, args=function_args, tool_context=tool_context)`. The
  parameter must be named `args`, not `tool_args`. Using the wrong name causes
  `TypeError: got an unexpected keyword argument 'args'`.
- Logs the tool name and arguments. During demos, this shows exactly what the
  LLM decided to call and with what parameters.

#### `logging_callback_after_tool` (lines 122–142)

```python
def logging_callback_after_tool(tool, args, tool_context, tool_response) -> None:
    console.print(f"✓ [{tool_name}] response_keys={list(tool_response.keys())}")
    return None
```

**Key points:**
- Logs only the **keys** of the response dict, not the full values — avoids
  flooding the console with large responses.
- Takes **four** parameters (adds `tool_response`) vs. three for `before_tool`.

---

### 3. Guardrail Callback (lines 145–188)

This is the most important callback for students to understand. It implements
**A2A feature F17 (Safety)**.

```python
_DANGEROUS_PATTERNS = [
    "os.system", "subprocess", "shutil.rmtree",
    "__import__", "exec(", "eval(", "open(",
]

def guardrail_callback_before_tool(tool, args, tool_context) -> Optional[dict]:
    code_arg = args.get("code", "")
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in code_arg:
            return {"error": f"Blocked: '{pattern}' is not allowed."}
    return None  # allow
```

**Explain to students:**

- **The pattern**: This callback inspects the `code` argument that the LLM
  provides when it calls a code-execution tool. If the code contains any
  dangerous pattern, the callback **blocks the call** by returning an error
  dict instead of `None`.
- **Why `return dict` vs `return None`?**: This is the key ADK convention.
  `None` = "proceed normally." A non-None return value = "use this as the
  tool's result instead of actually calling the tool."
- **The dangerous patterns**: Each one represents a way to escape a code
  sandbox:
  - `os.system` / `subprocess` — shell command execution
  - `shutil.rmtree` — recursive file deletion
  - `__import__` — dynamic module loading (could import anything)
  - `exec(` / `eval(` — arbitrary code execution
  - `open(` — file system access

**Teaching moment — limitations:**

- This is a **string-matching** guardrail, not an AST-based one. It can be
  bypassed (e.g., `getattr(os, 'system')('rm -rf /')` wouldn't be caught).
- Production guardrails should use AST parsing, sandboxed execution (gVisor,
  nsjail), or a dedicated code-scanning service.
- But the **pattern** is correct: intercept before execution, check against a
  policy, block if violated. The mechanism is sound; only the detection logic
  needs strengthening for production.

**How the code_agent wires it in:**

```python
agent = LlmAgent(
    ...,
    before_tool_callback=guardrail_callback_before_tool,
)
```

Just one line. The callback is automatically invoked before every tool call
the LLM makes.

---

### 4. Cache Callbacks (lines 191–247)

A pair of callbacks that implement a simple tool-result cache:

#### `cache_callback_before_tool` (lines 193–223)

```python
def cache_callback_before_tool(tool, args, tool_context) -> Optional[dict]:
    cache_key = f"{tool_name}:{sorted(args.items())}"
    if cache_key in _tool_cache:
        return _tool_cache[cache_key]  # cache HIT — skip tool execution
    return None  # cache MISS — execute tool normally
```

**Key points:**
- The cache key is `tool_name + sorted args`. Sorting ensures `{"a":1, "b":2}`
  and `{"b":2, "a":1}` produce the same key.
- If the key exists in `_tool_cache`, the cached result is **returned directly**,
  and the tool is **never called**. This is the interception pattern.
- `try/except TypeError` handles non-hashable arguments (e.g., lists or dicts
  as arg values) — just skip caching for those.

#### `cache_callback_after_tool` (lines 226–247)

```python
def cache_callback_after_tool(tool, args, tool_context, tool_response) -> None:
    cache_key = f"{tool_name}:{sorted(args.items())}"
    _tool_cache[cache_key] = tool_response
    return None
```

**Key points:**
- This callback **stores** results after a tool executes.
- Returns `None` — it doesn't modify the response, just caches it as a side
  effect.
- The before/after pair work together: `after` populates the cache, `before`
  reads from it.

**Teaching moment — limitations:**

- **No TTL**: Cached results never expire. The weather at 9am stays cached
  even at 5pm. Production caches need expiry policies.
- **No eviction**: The dict grows forever. Production needs a size limit (LRU).
- **Not thread-safe**: Concurrent requests could cause race conditions.
  Production needs `threading.Lock` or an external cache.
- **No invalidation**: If underlying data changes, stale results are served.

But the **architectural pattern** is valuable: transparent caching via
callbacks, with no changes to agent or tool code.

---

## How Agents Compose Callbacks

Show students how an agent combines multiple callbacks:

```python
agent = LlmAgent(
    name="code_agent",
    model=settings.GEMINI_MODEL,
    instruction="...",
    tools=[execute_code],
    before_model_callback=logging_callback_before_model,
    after_model_callback=logging_callback_after_model,
    before_tool_callback=guardrail_callback_before_tool,  # safety first
    after_tool_callback=logging_callback_after_tool,
)
```

**Note**: ADK allows only **one** callback per hook. If you need multiple
behaviors (e.g., both guardrail AND cache on `before_tool`), you compose them
into a single function:

```python
def combined_before_tool(tool, args, tool_context):
    # Guardrail first
    result = guardrail_callback_before_tool(tool, args, tool_context)
    if result is not None:
        return result  # blocked — don't even check cache
    # Then cache
    return cache_callback_before_tool(tool, args, tool_context)
```

---

## Design Patterns to Highlight

1. **Aspect-Oriented Programming**: Callbacks are cross-cutting concerns
   (logging, security, caching) applied without modifying core logic.

2. **Interceptor / Middleware Pattern**: Each callback can observe (return
   `None`) or intercept (return a value) the pipeline.

3. **Chain of Responsibility**: When composed, callbacks form a chain where
   each can short-circuit the rest.

4. **Defensive Programming**: `getattr(..., default)`, `try/except` with
   `pass`, type-checking `isinstance(tool_response, dict)` — callbacks must
   never crash the agent.

---

## Common Student Questions

1. **"Can I have async callbacks?"** ADK supports both sync and async callback
   functions. These are sync for simplicity, but you could use `async def` if
   your callback needs to make network calls.

2. **"What happens if a callback raises an exception?"** It depends on the ADK
   version, but generally the error propagates and the agent returns an error
   response. Callbacks should handle their own errors.

3. **"Can I use callbacks for rate limiting?"** Yes — a `before_model_callback`
   could check a token bucket and return a cached "please wait" response if
   the rate limit is exceeded. The callback pattern is generic.

4. **"Why not use FastAPI middleware instead?"** Middleware operates at the
   HTTP level; callbacks operate at the **agent logic** level. They intercept
   LLM calls and tool calls, not HTTP requests. Different layers, different
   concerns.

---

## Related Files

- `shared/config.py` — No direct dependency, but callbacks often access settings
- `code_agent/agent.py` — Uses `guardrail_callback_before_tool` for F17
- `weather_agent/agent.py` — Uses logging callbacks for observability
- `tests/test_shared_callbacks.py` — Unit tests for all callbacks
- `tests/test_shared_callbacks_extended.py` — Edge-case and integration tests
