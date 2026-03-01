# Speaker Notes — `loop_agent/agent.py`

> **File**: `loop_agent/agent.py` (128 lines)
> **Purpose**: LoopAgent polling pattern for monitoring async task lifecycle (submitted -> working -> completed).
> **Estimated teaching time**: 15–20 minutes

---

## Why This File Matters

This agent demonstrates **iterative orchestration** — a pattern where the same
sequence of operations repeats until an exit condition is met. This is
fundamentally different from the fixed-length pipeline (`pipeline_agent`) or
the one-shot parallel dispatch (`parallel_agent`).

The real-world use case: you submit a long-running task to an external service
and need to periodically check whether it is done. This is the **polling
pattern**, used everywhere in distributed systems:

- CI/CD: poll a build server until the job finishes
- Cloud APIs: poll a long-running operation endpoint
- A2A Protocol: poll an async agent for task status updates (F5 task lifecycle)

This file also demonstrates the A2A task lifecycle states
(`submitted`, `working`, `completed`, `failed`, `canceled`, `input-required`)
and how to build an exit condition evaluator as a separate agent.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–25)

```python
from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

from shared.config import settings
```

**Explain to students:**

- `LoopAgent` is the third orchestration primitive (alongside `SequentialAgent`
  and `ParallelAgent`). It repeats its sub-agents until an exit condition is
  met or `max_iterations` is reached.
- Two `RemoteA2aAgent` instances are needed — one for starting the task, one
  for polling. These are separate instances because they belong to different
  parent agents (same ADK ownership constraint as in `parallel_agent`).
- Both remote agents point to the same `ASYNC_AGENT_URL` — they talk to the
  same remote service but serve different purposes in the workflow.

---

### 2. Remote A2A Sub-Agents (lines 27–40)

```python
_async_agent_start = RemoteA2aAgent(
    name="async_agent_start",
    description="Sends a message to the async_agent to start a long-running task.",
    agent_card=f"{settings.ASYNC_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

_async_agent_poll = RemoteA2aAgent(
    name="async_agent_poll",
    description="Polls the async_agent for task status updates.",
    agent_card=f"{settings.ASYNC_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)
```

**Explain to students:**

- Two separate `RemoteA2aAgent` instances, both pointing to the same remote
  `async_agent`. Why two? Because `_async_agent_start` belongs to
  `start_task_agent` and `_async_agent_poll` belongs to `poll_agent`. The
  ADK one-parent constraint requires separate instances.
- The `agent_card` URL follows the A2A convention:
  `http://localhost:8005/.well-known/agent.json`. The remote agent's card
  describes its capabilities, supported protocols, and authentication
  requirements.
- The `description` field matters here — the parent LlmAgent uses it to
  decide which sub-agent to delegate to (though in this case each parent
  has only one sub-agent, so the choice is trivial).

---

### 3. Start Task Agent (lines 42–60)

```python
_START_TASK_INSTRUCTION = """
You are starting a long-running task on the async_agent.

1. Delegate to the async_agent_start sub-agent with the message:
   "Run a 20-second simulation task."
2. Extract the task_id from the response.
3. Store the task_id in your response for the polling loop to use.
"""

start_task_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="start_task_agent",
    description="Starts a long-running task on the async_agent.",
    instruction=_START_TASK_INSTRUCTION,
    sub_agents=[_async_agent_start],
    output_key="task_id",
)
```

**Explain to students:**

- This agent runs **once**, before the loop begins. Its job is to initiate the
  async task and capture the `task_id` for subsequent polling.
- `output_key="task_id"` stores the task identifier in session state. The
  polling agents inside the loop will read this to know which task to check.
- The instruction is explicit about the delegation pattern: (1) delegate to
  the remote agent, (2) extract the task_id, (3) store it. This step-by-step
  guidance helps the LLM produce reliable outputs.
- This maps to the A2A protocol's `message/send` endpoint — the initial
  request that starts the async workflow.

**Teaching moment**: The start-then-poll pattern requires the task initiation
to happen exactly once, outside the loop. If start were inside the loop, you
would create a new task on every iteration. The `SequentialAgent` root ensures
start runs first, then the loop begins.

---

### 4. Poll Agent (lines 62–87)

```python
_POLL_INSTRUCTION = """
You are a task poller. You have been given a task_id to monitor.

Delegate to the async_agent_poll sub-agent to check the task status.
Ask it: "Check the status of my task."

Interpret the response:
- If status.state is "completed": respond with "DONE: <result>"
- If status.state is "failed": respond with "FAILED: <error>"
- If status.state is "canceled": respond with "CANCELED"
- If status.state is "input-required": respond with "INPUT_REQUIRED: <message>"
- If status.state is "working" or "submitted": respond with "WORKING: <progress>"
"""

poll_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="poll_agent",
    description="Polls async_agent for task status updates.",
    instruction=_POLL_INSTRUCTION,
    sub_agents=[_async_agent_poll],
    output_key="poll_result",
)
```

**Explain to students:**

- The poll agent runs **every iteration** of the loop. It delegates to the
  remote `async_agent` to check the current task status.
- The instruction maps A2A task lifecycle states to standardized prefix strings
  (`DONE:`, `FAILED:`, `WORKING:`, etc.). This structured output makes it
  easy for the next agent (exit_check_agent) to parse the result.
- `output_key="poll_result"` stores the status string in session state after
  each poll. The exit_check_agent reads this key to decide whether to continue
  or exit.
- The `"input-required"` state is a unique A2A feature (F6 multi-turn) — the
  remote agent can pause and ask the user for additional information mid-task.

**Teaching moment**: Walk students through the A2A task lifecycle states:

```
submitted → working → completed
                   ↘ failed
                   ↘ canceled
                   ↘ input-required (paused, waiting for user)
```

These states are defined in the A2A protocol spec. The poll agent translates
protocol-level states into application-level signals that the exit checker
can act on.

---

### 5. Exit Condition Checker (lines 89–107)

```python
_EXIT_CHECK_INSTRUCTION = """
You are an exit condition checker for a polling loop.

Read the poll_result from state. Respond with exactly one word:
- "EXIT" if poll_result starts with "DONE:", "FAILED:", or "CANCELED"
- "CONTINUE" if poll_result starts with "WORKING:" or "INPUT_REQUIRED:"

Only respond with "EXIT" or "CONTINUE". No other text.
"""

exit_check_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="exit_check_agent",
    description="Checks whether the polling loop should exit.",
    instruction=_EXIT_CHECK_INSTRUCTION,
    output_key="should_exit",
)
```

**Explain to students:**

- This is the **exit condition evaluator** — a separate agent whose sole job
  is to decide whether the loop should continue or stop.
- The instruction constrains the output to exactly one word: `"EXIT"` or
  `"CONTINUE"`. This is critical because the `LoopAgent` checks
  `state["should_exit"]` for these exact strings to control loop behavior.
- `output_key="should_exit"` is the key the LoopAgent monitors. When this
  key contains `"EXIT"`, the loop terminates.
- Separating the exit condition into its own agent is a deliberate design
  choice. It keeps the poll agent focused on status retrieval and the exit
  checker focused on decision-making. Single responsibility principle.

**Teaching moment**: Why use an LLM agent for a simple string-prefix check?
In this demo, it is admittedly overkill — you could do this with a Python
function. But the pattern generalizes: in production, the exit condition might
require judgment ("is the quality of the result good enough to stop?"), and
an LLM-based evaluator handles that naturally. The demo establishes the pattern
with a simple case.

---

### 6. LoopAgent and Root Agent (lines 109–128)

```python
polling_loop = LoopAgent(
    name="polling_loop",
    description="Polls async_agent until task completes (max 10 iterations).",
    sub_agents=[poll_agent, exit_check_agent],
    max_iterations=10,
)

root_agent = SequentialAgent(
    name="loop_agent",
    description=(
        "Starts a long-running async task then polls until completion "
        "(max 10 iterations, 5-second intervals). Demonstrates LoopAgent."
    ),
    sub_agents=[start_task_agent, polling_loop],
)
```

**Explain to students:**

- `LoopAgent` repeats its `sub_agents` in order (poll, then check exit) on
  each iteration. It continues until either:
  (a) `state["should_exit"]` contains `"EXIT"`, or
  (b) `max_iterations=10` is reached (safety valve).
- `max_iterations` is essential — without it, a bug in the exit condition or
  a permanently-working task would cause an infinite loop. Always set a
  reasonable upper bound.
- The `sub_agents` order within the LoopAgent matters: poll first, then check.
  If you reversed them, the exit checker would evaluate stale data from the
  previous iteration (or no data on the first iteration).
- The root agent is a `SequentialAgent` with two steps:
  Step 1: `start_task_agent` (runs once — starts the async task)
  Step 2: `polling_loop` (runs repeatedly — polls until done)

**Teaching moment**: Draw the execution flow:

```
root_agent (SequentialAgent)
  │
  ├── start_task_agent          ← runs once
  │     └── [remote] async_agent → returns task_id
  │
  └── polling_loop (LoopAgent, max 10 iterations)
        │
        ├── poll_agent           ← iteration 1
        │     └── [remote] async_agent → "WORKING: 20%"
        ├── exit_check_agent     → "CONTINUE"
        │
        ├── poll_agent           ← iteration 2
        │     └── [remote] async_agent → "WORKING: 60%"
        ├── exit_check_agent     → "CONTINUE"
        │
        ├── poll_agent           ← iteration 3
        │     └── [remote] async_agent → "DONE: result data"
        └── exit_check_agent     → "EXIT"  ← loop terminates
```

Compare this to the pipeline_agent (fixed 3 stages, no repetition) and the
parallel_agent (one-shot concurrent execution, no iteration).

---

## Design Patterns to Highlight

1. **Polling Pattern**: Submit a long-running task, then periodically check its
   status until completion. This is the standard approach when push notifications
   are not available or when you need to control the polling interval.

2. **Separate Exit Condition Agent**: The decision to continue or stop the loop
   is delegated to a dedicated agent. This cleanly separates "gather data" from
   "evaluate data" — making each agent independently testable and replaceable.

3. **Safety Valve (max_iterations)**: Every LoopAgent should have a maximum
   iteration count. This prevents runaway loops from bugs, unresponsive remote
   services, or edge cases in exit logic.

4. **Session State as Loop Memory**: `output_key` writes to session state on
   every iteration. The exit checker reads the latest `poll_result` to make its
   decision. Session state acts as the shared memory across loop iterations.

5. **Start-Then-Poll Composition**: The root `SequentialAgent` ensures the task
   is started exactly once before polling begins. This is a common composition:
   one-time setup followed by iterative processing.

---

## Common Student Questions

1. **"How does the LoopAgent know when to stop?"** It checks the `should_exit`
   key in session state after each iteration. When `exit_check_agent` writes
   `"EXIT"` to `state["should_exit"]`, the LoopAgent detects this and
   terminates. The `max_iterations=10` provides a hard upper bound regardless
   of the exit condition.

2. **"What if the async task takes longer than 10 iterations?"** The loop
   exits at `max_iterations` and returns whatever the last `poll_result` was
   (likely `"WORKING: ..."`). The user would see that the task is still in
   progress. In production, you might retry with a longer timeout, increase
   `max_iterations`, or implement exponential backoff.

3. **"Why two separate RemoteA2aAgent instances for the same remote service?"**
   Same reason as in `parallel_agent`: ADK's one-parent ownership constraint.
   `_async_agent_start` belongs to `start_task_agent`, and `_async_agent_poll`
   belongs to `poll_agent`. They point to the same URL but are distinct Python
   objects.

4. **"Could the poll_agent and exit_check_agent be combined into one agent?"**
   Yes, technically. But separating them follows the single responsibility
   principle: polling is about gathering data, exit checking is about making a
   decision. In production, the exit condition might become complex (e.g.,
   "stop if quality score > 0.9 OR iterations > 5 OR budget exhausted"), and
   having it in a dedicated agent makes that logic easier to evolve.

5. **"What is the 'input-required' state?"** It is a unique A2A protocol
   feature (F6 multi-turn). The remote agent can pause mid-task and request
   additional information from the user. When the poll agent detects this
   state, the loop continues — but the LoopAgent will surface the request
   to the user before proceeding to the next iteration.

6. **"Is there any delay between polling iterations?"** Not in this
   implementation — the LoopAgent runs iterations back-to-back. In production,
   you would add a delay (e.g., 5 seconds) between iterations to avoid
   overwhelming the remote service. This could be done with a custom callback
   or by adding a delay agent between poll and check.

---

## Related Files

- `async_agent/agent.py` — The remote async agent that this loop agent polls;
  implements the task lifecycle (submitted -> working -> completed)
- `shared/config.py` — Provides `settings.ASYNC_AGENT_URL` and
  `settings.GEMINI_MODEL`
- `pipeline_agent/agent.py` — Contrast: fixed-length sequential execution,
  no iteration
- `parallel_agent/agent.py` — Contrast: concurrent execution, no iteration
- `orchestrator_agent/agent.py` — Contrast: LLM-driven routing with dynamic
  agent selection
- `webhook_server/main.py` — Alternative to polling: push-based notification
  when async tasks complete (A2A feature F11)
