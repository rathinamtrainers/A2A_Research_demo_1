# Speaker Notes — `pipeline_agent/agent.py`

> **File**: `pipeline_agent/agent.py` (117 lines)
> **Purpose**: 3-stage SequentialAgent implementing an assembly-line research pipeline: fetch, analyze, report.
> **Estimated teaching time**: 15–20 minutes

---

## Why This File Matters

This is the cleanest example of **deterministic multi-stage orchestration** in
the entire demo. No conditional branching, no loops, no remote calls — just
three LlmAgents executing in strict order, passing data forward through session
state. If a student is going to understand one orchestration pattern deeply,
this should be it.

The pipeline pattern shows up everywhere in production AI systems:

- RAG pipelines: retrieve -> rerank -> generate
- ETL pipelines: extract -> transform -> load
- Content pipelines: draft -> edit -> publish

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–28)

```python
from google.adk.agents import LlmAgent, SequentialAgent
from shared.config import settings

load_dotenv()
```

**Explain to students:**

- Only two agent types are imported: `LlmAgent` (individual stages) and
  `SequentialAgent` (the pipeline wrapper). This is the minimal import set
  for a sequential pipeline.
- `load_dotenv()` ensures `.env` variables are available before agent
  construction. The `settings` object from `shared/config.py` provides
  `GEMINI_MODEL`.
- No `RemoteA2aAgent` is needed here — every stage runs locally. This
  makes the pipeline agent a good "pure orchestration" example with no
  network dependencies.

---

### 2. Stage 1 — Fetch Agent (lines 30–52)

```python
_FETCH_INSTRUCTION = """
You are the Fetch stage of a research pipeline.

Your job: Given a topic from the user, write a comprehensive summary of
background information on that topic. Include key facts, definitions, and
relevant context.

Store your output in state key: "raw_data"

Format your response as:
TOPIC: <topic>
RAW_DATA: <your comprehensive summary>
"""

fetch_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="fetch_agent",
    description="Stage 1: Fetches and summarises raw information on a topic.",
    instruction=_FETCH_INSTRUCTION,
    output_key="raw_data",
)
```

**Explain to students:**

- The instruction tells the LLM what role it plays ("Fetch stage") and what
  format to produce. The structured format (`TOPIC:`, `RAW_DATA:`) makes
  downstream parsing more reliable.
- `output_key="raw_data"` is the critical mechanism. When this agent finishes,
  ADK automatically stores the agent's output text into
  `context.state["raw_data"]`. The next agent can then read that key.
- The `description` field is not just documentation — ADK uses it when a parent
  agent needs to decide which sub-agent to invoke. For SequentialAgent this
  matters less (execution order is fixed), but it is still good practice.

**Teaching moment**: `output_key` is the **inter-stage data bus** in ADK
sequential pipelines. Without it, you would need tool calls or custom callbacks
to pass data between stages. This is the simplest mechanism, and it works
because all agents in a SequentialAgent share the same session state.

---

### 3. Stage 2 — Analyze Agent (lines 54–80)

```python
_ANALYZE_INSTRUCTION = """
You are the Analyze stage of a research pipeline.

Your job: Take the raw_data from the previous stage (available in context)
and identify:
1. The 3-5 most important insights.
2. Any surprising or counterintuitive findings.
3. Key relationships and patterns.

Store your analysis in state key: "analysis"

Format your response as:
INSIGHTS:
1. ...
2. ...
PATTERNS: ...
"""

analyze_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="analyze_agent",
    description="Stage 2: Analyses raw data to extract key insights.",
    instruction=_ANALYZE_INSTRUCTION,
    output_key="analysis",
)
```

**Explain to students:**

- The instruction references "raw_data from the previous stage" — the LLM
  reads this from session state where Stage 1 stored it.
- `output_key="analysis"` stores this stage's output for Stage 3 to consume.
  At this point, session state contains both `raw_data` and `analysis`.
- The structured output format (numbered insights, patterns section) guides
  the LLM toward producing extractable content. This is a lightweight form
  of output schema enforcement without needing JSON mode.

**Teaching moment**: Notice the **progressive refinement** pattern. Stage 1
produces broad, raw information. Stage 2 distills it into structured insights.
Each stage adds value by narrowing focus. This is the essence of the pipeline
pattern — each stage has a single responsibility.

---

### 4. Stage 3 — Report Agent (lines 82–105)

```python
_REPORT_INSTRUCTION = """
You are the Report stage of a research pipeline.

Your job: Take the analysis from the previous stage and produce a polished,
professional research report.

The report must include:
- Executive Summary (2-3 sentences)
- Key Findings (bullet points)
- Analysis Section (prose)
- Conclusion

Format as proper markdown with headings.
"""

report_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="report_agent",
    description="Stage 3: Formats analysis into a structured markdown report.",
    instruction=_REPORT_INSTRUCTION,
    output_key="final_report",
)
```

**Explain to students:**

- Stage 3 reads the `analysis` key from session state and transforms it into
  a user-facing deliverable — a properly formatted markdown report.
- `output_key="final_report"` stores the finished report in session state.
  This is the terminal output key; the SequentialAgent will present the
  last agent's output as its overall response.
- The instruction specifies a precise document structure (Executive Summary,
  Key Findings, Analysis, Conclusion). This acts as a template for the LLM.

**Teaching moment**: The three stages mirror a real editorial workflow:
researcher (fetch) -> analyst (analyze) -> writer (report). In production,
you might use different models for different stages — a cheap fast model for
fetching, a reasoning model for analysis, and a creative model for report
writing. ADK makes this trivial: just change `model=` per agent.

---

### 5. Root Agent — SequentialAgent (lines 107–117)

```python
root_agent = SequentialAgent(
    name="pipeline_agent",
    description=(
        "3-stage research pipeline: (1) Fetch -> (2) Analyze -> (3) Report. "
        "Run with: adk run ./pipeline_agent/"
    ),
    sub_agents=[fetch_agent, analyze_agent, report_agent],
)
```

**Explain to students:**

- `SequentialAgent` executes `sub_agents` in list order, one after another.
  There is no conditional logic, no branching, no parallelism. The execution
  order is **deterministic** — it always runs fetch, then analyze, then report.
- The variable must be named `root_agent` — this is an ADK convention. When
  you run `adk run ./pipeline_agent/`, ADK looks for `root_agent` in the
  `agent.py` module.
- `SequentialAgent` does **not** have a `model` parameter. It is a pure
  orchestration wrapper — it contains no LLM of its own. Only the child
  `LlmAgent` stages invoke the LLM.
- The `sub_agents` list order defines the execution order. Swapping the order
  would break the pipeline because each stage depends on the previous stage's
  output.

**Teaching moment**: Compare this to code:

```python
# This is conceptually what SequentialAgent does:
raw_data = await fetch_agent.run(user_input)
state["raw_data"] = raw_data

analysis = await analyze_agent.run(state)
state["analysis"] = analysis

final_report = await report_agent.run(state)
state["final_report"] = final_report
```

The advantage of the declarative SequentialAgent approach: ADK handles session
state, error propagation, logging, and tracing automatically. You declare the
pipeline structure; ADK manages the execution.

---

## Design Patterns to Highlight

1. **Assembly-Line Pattern**: Each stage has a single responsibility and
   produces a well-defined output. The stages are loosely coupled — they
   communicate only through session state keys, not direct function calls.

2. **Session State as Data Bus**: `output_key` is the mechanism for inter-stage
   data passing. Each agent writes to a named key; subsequent agents read from
   it. This avoids direct coupling between stages.

3. **Progressive Refinement**: Raw data -> structured insights -> polished
   report. Each stage adds value by transforming and narrowing the previous
   stage's output.

4. **Declarative Orchestration**: The pipeline structure is defined by the
   `sub_agents` list, not by imperative control flow. This makes the pipeline
   easy to read, modify (add/remove stages), and reason about.

5. **Separation of Concerns**: The instruction for each stage mentions only
   its own responsibility. Stage 2 does not know how Stage 1 fetched the data.
   Stage 3 does not know how Stage 2 analyzed it. Each stage is independently
   testable.

---

## Common Student Questions

1. **"How does Stage 2 actually read Stage 1's output?"** Through session
   state. When `fetch_agent` finishes, ADK stores its output in
   `context.state["raw_data"]` (because of `output_key="raw_data"`). The
   `analyze_agent`'s LLM call includes the full session state as context,
   so it can see the `raw_data` value. The instruction tells the LLM to
   look for it.

2. **"What happens if Stage 1 fails or produces garbage?"** The pipeline
   continues regardless — `SequentialAgent` does not validate intermediate
   outputs. The analyze stage will do its best with whatever it receives.
   In production, you would add validation agents or guardrails between stages.

3. **"Can I add more stages?"** Yes. Just create another `LlmAgent` with
   its own `output_key` and insert it into the `sub_agents` list at the
   desired position. The pipeline is extensible by design.

4. **"Why not use a single agent with a long prompt?"** Three reasons:
   (a) separation of concerns makes each stage easier to debug and test,
   (b) you can use different models per stage for cost/quality tradeoffs,
   (c) intermediate outputs are observable in session state for monitoring.

5. **"Could this pipeline call remote agents instead of local LlmAgents?"**
   Absolutely. Replace any `LlmAgent` stage with an `LlmAgent` that has a
   `RemoteA2aAgent` as a sub-agent. The pipeline pattern is orthogonal to
   local vs. remote execution.

---

## Related Files

- `shared/config.py` — Provides `settings.GEMINI_MODEL` used by all three stages
- `parallel_agent/agent.py` — Contrast: uses `ParallelAgent` for fan-out instead
  of sequential execution
- `loop_agent/agent.py` — Contrast: uses `LoopAgent` for iterative polling instead
  of fixed-length sequences
- `orchestrator_agent/agent.py` — Contrast: uses an LLM-driven router instead of
  deterministic ordering
- `tests/` — Integration tests that exercise the pipeline end-to-end
