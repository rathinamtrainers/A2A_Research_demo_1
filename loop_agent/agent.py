"""
Loop Agent — LoopAgent polling async_agent until a task completes.

Demonstrates:
  F5  — Task Lifecycle polling: submitted → working → completed
  F6  — Multi-turn: loop continues requesting input if needed
  F10 — LoopAgent with max_iterations exit condition

The loop agent polls the async_agent's ``tasks/get`` endpoint every
5 seconds (up to 10 iterations) until the task is in a terminal state.

It also demonstrates F6 (input-required) by pausing when the task enters
``input-required`` state and asking the user for more information.

Usage::

    adk run ./loop_agent/
"""

from __future__ import annotations

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent

from shared.config import settings

load_dotenv()

# ── Polling sub-agent ─────────────────────────────────────────────────────────

_POLL_INSTRUCTION = """
You are a task poller. You have been given a task_id to monitor.

Use the provided task_id to call the async_agent's tasks/get endpoint:
  POST {async_agent_url}/ with method "tasks/get" and params {{"id": task_id}}

Interpret the response:
- If status.state is "completed": respond with "DONE: <result>"
- If status.state is "failed": respond with "FAILED: <error>"
- If status.state is "canceled": respond with "CANCELED"
- If status.state is "input-required": respond with "INPUT_REQUIRED: <message>"
  (the LoopAgent will pause and ask the user for input)
- If status.state is "working" or "submitted": respond with "WORKING: <progress>"
  (the LoopAgent will continue polling)

async_agent URL: {async_agent_url}
""".format(async_agent_url=settings.ASYNC_AGENT_URL)

poll_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="poll_agent",
    description="Polls async_agent for task status updates.",
    instruction=_POLL_INSTRUCTION,
    output_key="poll_result",
)

# ── Exit condition checker ────────────────────────────────────────────────────

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

# ── LoopAgent (F10) ───────────────────────────────────────────────────────────

polling_loop = LoopAgent(
    name="polling_loop",
    description="Polls async_agent until task completes (max 10 iterations).",
    sub_agents=[poll_agent, exit_check_agent],
    max_iterations=10,
)

# ── Root: start task then poll ────────────────────────────────────────────────

_START_TASK_INSTRUCTION = """
You are starting a long-running task on the async_agent.

1. Send a message/send request to {url}/ to start a new task.
   The message should be: "Run a 20-second simulation task."
2. Extract the task_id from the response.
3. Store the task_id in state key "task_id" for the polling loop.

async_agent URL: {url}
""".format(url=settings.ASYNC_AGENT_URL)

start_task_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="start_task_agent",
    description="Starts a long-running task on the async_agent.",
    instruction=_START_TASK_INSTRUCTION,
    output_key="task_id",
)

from google.adk.agents import SequentialAgent

root_agent = SequentialAgent(
    name="loop_agent",
    description=(
        "Starts a long-running async task then polls until completion "
        "(max 10 iterations, 5-second intervals). Demonstrates LoopAgent."
    ),
    sub_agents=[start_task_agent, polling_loop],
)
