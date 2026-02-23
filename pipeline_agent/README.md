# pipeline_agent/

A `SequentialAgent` that chains 3 LLM stages in an assembly-line pattern:
**Fetch → Analyze → Report**.

Each stage reads the previous stage's output from shared session state,
demonstrating state passing in ADK pipelines.

## Features Demonstrated

| Feature | Description |
|---|---|
| F10 — SequentialAgent | Deterministic stage-by-stage execution |
| F13 — Session State | Output of each stage stored in `context.state` and read by the next |

## Stages

1. **fetch_agent** — Summarises background information on the topic → `state["raw_data"]`
2. **analyze_agent** — Extracts key insights from raw data → `state["analysis"]`
3. **report_agent** — Formats analysis into a polished markdown report → `state["final_report"]`

## Running Locally

```bash
# Interactive terminal chat:
adk run ./pipeline_agent/

# Browser Dev UI:
adk web ./pipeline_agent/
```

## Example Interaction

```
You: Research the history of the A2A protocol
Pipeline: [Stage 1: Fetch] → [Stage 2: Analyze] → [Stage 3: Report]
Output: A structured markdown research report
```
