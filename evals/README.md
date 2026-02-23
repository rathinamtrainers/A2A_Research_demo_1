# evals/

ADK evaluation datasets and configuration for measuring agent quality.

Reference: F18 — Evaluation Framework.

## Files

| File | Description |
|---|---|
| `orchestrator_eval.json` | Multi-turn eval: routing accuracy, tool use, multi-agent delegation |
| `weather_eval.json` | Weather agent: tool call accuracy, response completeness |
| `eval_config.yaml` | Evaluation criteria, weights, thresholds, and output config |

## Running Evaluations

```bash
# Evaluate orchestrator agent:
adk eval ./evals/orchestrator_eval.json \
    --config ./evals/eval_config.yaml \
    --agent ./orchestrator_agent/

# Evaluate weather agent:
adk eval ./evals/weather_eval.json \
    --config ./evals/eval_config.yaml \
    --agent ./weather_agent/

# Or run all evals via pytest:
pytest tests/ -m eval -v
```

## Eval Dataset Format

Each `.json` file contains an `evals` array of test cases. Each test has:

```json
{
  "name": "test_name",
  "description": "...",
  "conversation": [
    {
      "invocation_id": "unique_id",
      "user_content": { "role": "user", "parts": [...] },
      "expected_tool_use": [{ "tool_name": "...", "tool_input": {} }],
      "reference": "Expected response description for scoring"
    }
  ]
}
```

## Metrics

| Metric | Description | Weight |
|---|---|---|
| `tool_trajectory_avg_score` | Did agent call right tools with right args? | 40% |
| `response_match_score` | Is response correct and complete? | 40% |
| `safety_score` | Did agent avoid dangerous tool calls? | 20% |

## Adding New Evals

1. Create a new `.json` file following the format above.
2. Add corresponding test cases in `tests/` with `@pytest.mark.eval`.
3. Run with `adk eval` or `pytest`.
