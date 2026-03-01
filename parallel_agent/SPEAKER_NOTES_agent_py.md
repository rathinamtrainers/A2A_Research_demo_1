# Speaker Notes — `parallel_agent/agent.py`

> **File**: `parallel_agent/agent.py` (96 lines)
> **Purpose**: Concurrent weather queries for 5 cities using ParallelAgent fan-out/fan-in with remote A2A delegation.
> **Estimated teaching time**: 15–20 minutes

---

## Why This File Matters

This agent demonstrates two powerful ADK concepts working together:

1. **ParallelAgent** (fan-out/fan-in) — running multiple sub-agents concurrently.
2. **RemoteA2aAgent** — each sub-agent delegates to a remote weather service via
   the A2A protocol.

The real-world analogy: you need weather data for 5 cities. Instead of querying
them one by one (sequential), you send all 5 requests simultaneously (parallel)
and aggregate when all return. This is the **scatter-gather** or **fan-out/fan-in**
pattern, fundamental to distributed systems.

This file also surfaces a critical ADK constraint that trips up many developers:
an agent instance can only belong to one parent. Understanding why the factory
function exists is key to working with ParallelAgent in ADK.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–24)

```python
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

from shared.config import settings
```

**Explain to students:**

- Three orchestration types are imported: `LlmAgent` (individual city agents),
  `ParallelAgent` (concurrent execution), and `SequentialAgent` (root wrapper
  for parallel + aggregation).
- `RemoteA2aAgent` is the ADK class that implements A2A protocol client
  behavior. It takes an agent card URL, discovers the remote agent's
  capabilities, and delegates work to it.
- `AGENT_CARD_WELL_KNOWN_PATH` is the string `"/.well-known/agent.json"` — the
  standard A2A discovery endpoint. Every A2A-compliant server hosts its agent
  card at this path.

---

### 2. The City Agent Factory (lines 26–53)

```python
_CITIES = ["London", "Tokyo", "New York", "Sydney", "Paris"]

def _make_city_agent(city: str) -> LlmAgent:
    """Create an LlmAgent (with its own RemoteA2aAgent) for a specific city."""
    city_slug = city.lower().replace(" ", "_")
    city_weather_remote = RemoteA2aAgent(
        name=f"weather_agent_{city_slug}",
        description=f"Fetches current weather conditions for {city}.",
        agent_card=f"{settings.WEATHER_AGENT_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    return LlmAgent(
        model=settings.GEMINI_MODEL,
        name=f"weather_{city_slug}",
        description=f"Fetches weather for {city}.",
        instruction=f"Ask the weather_agent for the current weather in {city}. "
                    f"Return a one-line summary: '{city}: <temp>°C, <conditions>'.",
        sub_agents=[city_weather_remote],
        output_key=f"weather_{city_slug}",
    )

city_agents = [_make_city_agent(city) for city in _CITIES]
```

**Explain to students:**

- **Why a factory function?** This is the most important design decision in
  this file. Each city agent needs its **own** `RemoteA2aAgent` instance. You
  cannot share a single `RemoteA2aAgent` across multiple parent agents.
- **The ADK constraint**: In ADK, an agent instance can only belong to one
  parent. When you add an agent to a parent's `sub_agents` list, ADK sets the
  agent's `.parent` attribute. If you tried to add the same `RemoteA2aAgent`
  instance to 5 different `LlmAgent` parents, only the last assignment would
  stick — the first 4 would lose their reference.
- **city_slug** converts "New York" to "new_york" for use in agent names and
  state keys. Agent names must be valid identifiers (no spaces).
- **output_key** is unique per city: `weather_london`, `weather_tokyo`, etc.
  After the parallel execution, session state contains all 5 results.
- **instruction** is city-specific — each agent is hard-coded to ask about
  one particular city. This is the fan-out: the same operation parameterized
  across 5 inputs.

**Teaching moment**: The factory pattern here is not just a code style
preference — it is required by ADK's ownership model. Draw the object graph:

```
ParallelAgent
  ├── LlmAgent("weather_london")
  │     └── RemoteA2aAgent("weather_agent_london")  ← unique instance
  ├── LlmAgent("weather_tokyo")
  │     └── RemoteA2aAgent("weather_agent_tokyo")    ← unique instance
  ├── LlmAgent("weather_new_york")
  │     └── RemoteA2aAgent("weather_agent_new_york") ← unique instance
  ...
```

All 5 `RemoteA2aAgent` instances point to the same URL (`WEATHER_AGENT_URL`),
but they are distinct Python objects with distinct parents.

---

### 3. Aggregator Agent (lines 55–74)

```python
_AGGREGATOR_INSTRUCTION = """
You have received weather data for 5 cities from the parallel sub-agents.
Summarise the results in a clean table:

| City       | Temperature | Conditions |
|------------|-------------|------------|
| London     | ...         | ...        |
| ...

Then identify the warmest and coldest city.
"""

aggregator_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="weather_aggregator",
    description="Combines parallel weather results into a summary table.",
    instruction=_AGGREGATOR_INSTRUCTION,
)
```

**Explain to students:**

- This is the **fan-in** stage. After all 5 city agents complete, the
  aggregator reads their results from session state and produces a unified
  summary.
- The instruction includes a markdown table template, guiding the LLM toward
  the desired output format.
- The aggregator does not have `output_key` — its output goes directly to the
  user as the final response.
- Notice the aggregator has no `sub_agents`. It does not delegate to anyone. It
  purely synthesizes data that already exists in session state.

**Teaching moment**: The fan-in agent is where you add business logic. In this
case, it is simple (make a table, find extremes). In production, the aggregator
might apply ranking, filtering, deduplication, or conflict resolution across
the parallel results.

---

### 4. ParallelAgent and Root Agent (lines 76–96)

```python
parallel_weather = ParallelAgent(
    name="parallel_weather",
    description="Fetches weather for 5 cities simultaneously.",
    sub_agents=city_agents,
)

root_agent = SequentialAgent(
    name="parallel_agent",
    description=(
        "Fetches weather for 5 cities in parallel, then summarises results. "
        "Demonstrates ParallelAgent fan-out/fan-in pattern."
    ),
    sub_agents=[parallel_weather, aggregator_agent],
)
```

**Explain to students:**

- `ParallelAgent` runs all 5 `city_agents` concurrently. It waits for all of
  them to finish before proceeding. This is an **all-or-nothing** parallel
  execution — there is no partial-result handling.
- Like `SequentialAgent`, `ParallelAgent` has no `model` parameter. It is a
  pure orchestration primitive — no LLM of its own.
- The root agent is a `SequentialAgent` wrapping two steps:
  Step 1: `parallel_weather` (runs 5 city agents concurrently)
  Step 2: `aggregator_agent` (summarizes the results)
- This is the **fan-out/fan-in** pattern composed from two orchestration
  primitives: `ParallelAgent` for the fan-out, `SequentialAgent` for the
  sequential aggregation afterward.

**Teaching moment**: Draw the execution timeline:

```
Time  ─────────────────────────────────────────────>

      ┌── weather_london ──────┐
      ├── weather_tokyo ───────┤
      ├── weather_new_york ────┤  → aggregator_agent → response
      ├── weather_sydney ──────┤
      └── weather_paris ───────┘

      ←── ParallelAgent ──────→  ←─ Sequential ────→
```

Compare with the pipeline_agent, which would be:

```
      london → tokyo → new_york → sydney → paris → aggregator
```

If each city query takes 2 seconds, the parallel version takes ~2 seconds
total; the sequential version takes ~10 seconds. This is why ParallelAgent
matters.

---

## Design Patterns to Highlight

1. **Fan-Out / Fan-In (Scatter-Gather)**: ParallelAgent fans out to N sub-agents
   concurrently, then a downstream aggregator collects and synthesizes the
   results. This is a fundamental distributed systems pattern.

2. **Factory Function for Agent Instances**: The `_make_city_agent()` factory
   ensures each city gets its own agent instances, respecting ADK's one-parent
   ownership constraint. This pattern is reusable whenever you need N similar
   agents.

3. **Composed Orchestration Primitives**: The root agent is a `SequentialAgent`
   containing a `ParallelAgent` and an `LlmAgent`. ADK's orchestration types
   are composable — you can nest them to build complex workflows from simple
   building blocks.

4. **Remote Delegation with Local Orchestration**: The orchestration logic
   (parallel execution, aggregation) runs locally. The actual work (fetching
   weather) is delegated to a remote A2A agent. This separation means you
   can change the remote agent's implementation without touching the
   orchestration code.

5. **Parameterized Sub-Agents**: Each city agent is the same template
   parameterized with a different city name. The factory function makes this
   DRY. In production, the parameter list might come from a database or
   configuration file.

---

## Common Student Questions

1. **"Why can't I share one RemoteA2aAgent across all 5 city agents?"** ADK's
   agent tree is a strict hierarchy — each agent has exactly one parent. When
   you assign an agent to a parent's `sub_agents`, ADK sets `agent.parent`.
   Sharing an instance would mean the last parent to claim it wins, and the
   others silently lose their sub-agent. The factory function avoids this by
   creating fresh instances.

2. **"What happens if one city query fails?"** ParallelAgent waits for all
   sub-agents to complete. If one fails, the error propagates. There is no
   built-in partial-result handling or timeout per sub-agent. In production,
   you might add error-handling wrappers or use `asyncio.gather(return_exceptions=True)`
   style patterns at a lower level.

3. **"Why is the root agent a SequentialAgent and not just a ParallelAgent?"**
   Because the aggregation must happen **after** all parallel queries complete.
   ParallelAgent alone would run all sub-agents (including the aggregator)
   simultaneously — the aggregator would have no data to work with. The
   SequentialAgent enforces the order: first parallel fetch, then aggregate.

4. **"Could I dynamically change the list of cities?"** Yes. Since
   `_make_city_agent()` is a plain Python function and `_CITIES` is a list,
   you could load the cities from a config file, database, or user input.
   The factory pattern makes this straightforward.

5. **"Does each RemoteA2aAgent open its own connection to the weather service?"**
   Yes. Each instance independently discovers the agent card and establishes
   its own communication channel. In a production scenario with many cities,
   you might want connection pooling at a lower layer.

---

## Related Files

- `weather_agent/agent.py` — The remote weather service that all 5 city agents
  delegate to via A2A
- `shared/config.py` — Provides `settings.WEATHER_AGENT_URL` and
  `settings.GEMINI_MODEL`
- `pipeline_agent/agent.py` — Contrast: pure sequential execution, no parallelism
- `loop_agent/agent.py` — Contrast: iterative execution with exit conditions
- `orchestrator_agent/agent.py` — Contrast: LLM-driven routing rather than
  static fan-out
