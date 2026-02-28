"""
Loop Agent — LoopAgent polling async_agent until a task completes.

Demonstrates:
  F5  — Task Lifecycle polling: submitted → working → completed
  F6  — Multi-turn: loop continues requesting input if needed
  F10 — LoopAgent with max_iterations exit condition

The loop agent delegates to the async_agent via RemoteA2aAgent sub-agents:
  1. ``start_task_agent`` sends a message/send request to start a task
  2. ``poll_agent`` sends tasks/get requests to check progress

Usage::

    adk run ./loop_agent/
"""

from __future__ import annotations

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

from shared.config import settings

load_dotenv()

# ── Remote A2A sub-agents for communicating with async_agent ─────────────────

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

# ── Start task sub-agent ─────────────────────────────────────────────────────

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

# ── Polling sub-agent ────────────────────────────────────────────────────────

_POLL_INSTRUCTION = """
You are a task poller. You have been given a task_id to monitor.

Delegate to the async_agent_poll sub-agent to check the task status.
Ask it: "Check the status of my task."

Interpret the response:
- If status.state is "completed": respond with "DONE: <result>"
- If status.state is "failed": respond with "FAILED: <error>"
- If status.state is "canceled": respond with "CANCELED"
- If status.state is "input-required": respond with "INPUT_REQUIRED: <message>"
  (the LoopAgent will pause and ask the user for input)
- If status.state is "working" or "submitted": respond with "WORKING: <progress>"
  (the LoopAgent will continue polling)
"""

poll_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="poll_agent",
    description="Polls async_agent for task status updates.",
    instruction=_POLL_INSTRUCTION,
    sub_agents=[_async_agent_poll],
    output_key="poll_result",
)

# ── Exit condition checker ───────────────────────────────────────────────────

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

# ── LoopAgent (F10) ─────────────────────────────────────────────────────────

polling_loop = LoopAgent(
    name="polling_loop",
    description="Polls async_agent until task completes (max 10 iterations).",
    sub_agents=[poll_agent, exit_check_agent],
    max_iterations=10,
)

# ── Root: start task then poll ───────────────────────────────────────────────

root_agent = SequentialAgent(
    name="loop_agent",
    description=(
        "Starts a long-running async task then polls until completion "
        "(max 10 iterations, 5-second intervals). Demonstrates LoopAgent."
    ),
    sub_agents=[start_task_agent, polling_loop],
)
