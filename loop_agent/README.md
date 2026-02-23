# loop_agent/

A `LoopAgent` that polls `async_agent` for task completion status,
iterating until the task reaches a terminal state or the maximum
iteration count is reached.

## Features Demonstrated

| Feature | Description |
|---|---|
| F5 — Task Lifecycle | Monitors the full state machine: working → completed |
| F6 — Multi-turn | Handles `input-required` by pausing for user input |
| F10 — LoopAgent | Max 10 iterations with configurable exit condition |

## Architecture

```
SequentialAgent (root_agent)
  ├── LlmAgent (start_task_agent)   → starts task on async_agent, stores task_id
  └── LoopAgent (polling_loop)       → repeats until EXIT condition
        ├── LlmAgent (poll_agent)         → calls tasks/get, stores poll_result
        └── LlmAgent (exit_check_agent)   → returns EXIT or CONTINUE
```

## Running Locally

```bash
# Requires async_agent running at http://localhost:8005
uvicorn async_agent.agent:app --port 8005

adk run ./loop_agent/
```
