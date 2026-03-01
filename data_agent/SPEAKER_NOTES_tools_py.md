# Speaker Notes — `data_agent/tools.py`

> **File**: `data_agent/tools.py` (152 lines)
> **Purpose**: Data processing tool functions for CSV parsing, statistics, and Artifact generation.
> **Estimated teaching time**: 12–15 minutes
> **A2A Features covered**: F12 (Function Tools), F15 (Artifacts)

---

## Why This File Matters

This file demonstrates two fundamental ADK patterns:

1. **Function Tools (F12)**: Plain Python functions that the LLM can call.
   ADK automatically generates JSON Schema from the function signatures and
   docstrings, registers them with the model, and handles serialization of
   return values. No decorators, no base classes, no boilerplate — just
   functions that return dicts.

2. **Artifact Generation (F15)**: The `generate_csv_report` function shows
   how to produce file-like output from a tool. The function returns a dict
   with `filename`, `mime_type`, and `content` keys. The ADK framework picks
   this up and exposes it as an A2A `FilePart` Artifact that clients can
   download.

This is also the cleanest example of **pure standard library code** in the
project. Every import (`csv`, `io`, `json`, `statistics`) is from Python's
standard library. No third-party dependencies, no GCP libraries, no ADK
imports. The tools are completely framework-agnostic — you could use them in
a Flask app, a CLI script, or a Jupyter notebook without any changes.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–18)

```python
"""
Data processing tools for the Data Agent.

All tools return standard Python dicts so ADK can serialise them as
JSON in the model's context.  The ``generate_csv_report`` tool also
demonstrates the pattern for returning file content that the agent
framework can expose as an A2A Artifact.

Reference: F12 — Function Tools; F15 — Artifacts.
"""

import csv
import io
import json
import statistics
from typing import Any
```

**Explain to students:**

- **All standard library**: No external dependencies. This is intentional.
  Tool functions should be **pure business logic** — no framework coupling,
  no cloud SDK dependencies. This makes them easy to unit test and reuse.
- **`io.StringIO`**: Used to create in-memory file-like objects for the `csv`
  module. Instead of writing to disk, we write to a string buffer and extract
  the result with `.getvalue()`.
- **`statistics`**: Python's built-in statistics module. It provides `mean`,
  `median`, `stdev`, and other descriptive statistics. For a demo, this is
  perfect — no need for NumPy or pandas.
- **Return convention**: The docstring states it clearly — all tools return
  `dict`. ADK serializes these as JSON in the model's context. This is the
  standard ADK function tool contract.

---

### 2. Delimiter Auto-Detection (lines 21–39)

```python
def _detect_delimiter(csv_text: str) -> str:
    first_line = csv_text.split("\n")[0] if csv_text else ""
    if "\t" in first_line:
        return "\t"
    if ";" in first_line:
        return ";"
    return ","
```

**Explain to students:**

- **Private function** (leading underscore): This is a helper, not a tool.
  The LLM never sees it. Only public functions registered in
  `agent.py`'s `tools=[...]` list are exposed to the model.
- **Detection order**: Tab first, then semicolon, then comma as fallback.
  This order is intentional:
  - Tab-delimited files (TSV) are common in data science and bioinformatics.
  - Semicolon-delimited files are common in European locales where comma is
    the decimal separator (e.g., `1,5` means 1.5).
  - Comma is the default/fallback for standard CSV.
- **First-line heuristic**: Only examines the header row. This is a simple
  but effective approach. A more robust implementation would use Python's
  `csv.Sniffer` class, which samples multiple lines and uses statistical
  analysis to guess the delimiter.

**Teaching moment**: This function demonstrates the "convention over
configuration" principle. Rather than requiring the user to specify the
delimiter, the tool infers it. This makes the LLM's job easier — it does
not need to figure out or ask about the delimiter format.

---

### 3. CSV Parsing Tool (lines 42–71)

```python
def parse_csv_data(csv_text: str) -> dict:
    try:
        stripped = csv_text.strip()
        delimiter = _detect_delimiter(stripped)
        reader = csv.DictReader(io.StringIO(stripped), delimiter=delimiter)
        rows = list(reader)
        columns = reader.fieldnames or []
        return {
            "columns": list(columns),
            "rows": rows,
            "row_count": len(rows),
            "delimiter": delimiter,
        }
    except Exception as exc:
        return {"error": f"Failed to parse CSV: {exc}"}
```

**Explain to students:**

- **`csv.DictReader`**: Reads CSV rows as dictionaries (`{column_name: value}`).
  This is more useful than `csv.reader` (which returns lists) because the
  output is self-describing — each row carries its column names.
- **`io.StringIO`**: Wraps the input string in a file-like object that
  `csv.DictReader` can iterate over. This avoids writing to a temporary file.
- **Return structure**: The dict contains four keys:
  - `columns` — the header names (list of strings)
  - `rows` — the parsed data (list of dicts)
  - `row_count` — convenience field so the LLM can report the count without
    counting the list
  - `delimiter` — the auto-detected delimiter, useful for debugging
- **Error handling pattern**: The `try/except` returns `{"error": ...}`
  instead of raising an exception. This is the **ADK function tool contract**.
  The LLM receives the error dict as the tool result and can report the
  error to the user in natural language. If the function raised an exception
  instead, ADK would catch it, but the error message would be less
  informative.

**Teaching moment**: Notice that `reader.fieldnames` is accessed **after**
`list(reader)`. This is a subtle `csv.DictReader` behavior: `fieldnames` is
populated lazily on the first iteration. Calling `list(reader)` forces
iteration, which populates `fieldnames`. The `or []` fallback handles the
edge case of an empty input.

---

### 4. Statistics Computation Tool (lines 74–110)

```python
def compute_statistics(data: str) -> dict:
    try:
        parsed: Any = json.loads(data)
        if isinstance(parsed, list) and all(isinstance(x, (int, float)) for x in parsed):
            nums = [float(x) for x in parsed]
        elif isinstance(parsed, list) and all(isinstance(x, dict) for x in parsed):
            nums = [float(row["value"]) for row in parsed if "value" in row]
        else:
            return {"error": "Expected a JSON list of numbers or objects with 'value' key."}

        if not nums:
            return {"error": "No numeric data to compute statistics on."}

        return {
            "count": len(nums),
            "mean": round(statistics.mean(nums), 4),
            "median": round(statistics.median(nums), 4),
            "stdev": round(statistics.stdev(nums), 4) if len(nums) > 1 else 0.0,
            "min": min(nums),
            "max": max(nums),
            "sum": round(sum(nums), 4),
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return {"error": f"Statistics computation failed: {exc}"}
```

**Explain to students:**

- **Input format**: The function takes a **JSON string**, not a Python list.
  This is because ADK function tool parameters are always strings or
  primitives when passed from the LLM. The LLM generates a JSON array as a
  string, and this function parses it.
- **Dual input support**: Two formats are accepted:
  1. A flat list of numbers: `[1, 2, 3, 4, 5]`
  2. A list of objects with a `value` key: `[{"name": "A", "value": 10}, ...]`

  The second format is common when the data comes from `parse_csv_data` —
  the parsed CSV rows are dicts, and one column contains the numeric values.

- **`statistics.stdev` guard** (line 104): Standard deviation requires at
  least 2 data points (it divides by `n-1`). With a single value, `stdev()`
  raises `StatisticsError`. The `if len(nums) > 1 else 0.0` guard prevents
  this edge case crash.

- **Rounding to 4 decimal places**: Prevents floating-point noise in the
  output. Without rounding, `statistics.mean([1, 2, 3])` might return
  `2.0000000000000004`. The LLM would then report this noisy value to the
  user.

- **Specific exception types** (line 109): Unlike `parse_csv_data` which
  catches broad `Exception`, this function catches only `json.JSONDecodeError`,
  `KeyError`, `TypeError`, and `ValueError`. This is more precise — it
  catches the specific failures that can occur during JSON parsing and numeric
  conversion, while letting unexpected errors (e.g., `MemoryError`) propagate.

**Teaching moment**: Ask students why `data` is typed as `str` and not
`list[float]`. The answer: LLMs generate tool arguments as strings. Even if
the LLM "knows" it is passing a list, the underlying function call mechanism
transmits it as a JSON-encoded string. The tool must deserialize it. This is
a common source of confusion for students coming from typed API frameworks.

---

### 5. CSV Report Generation Tool (lines 113–152)

```python
def generate_csv_report(title: str, columns: str, rows_json: str) -> dict:
    try:
        col_list = [c.strip() for c in columns.split(",")]
        row_data: list[list] = json.loads(rows_json)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(col_list)
        for row in row_data:
            writer.writerow(row)

        csv_content = output.getvalue()
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)

        return {
            "filename": f"{safe_title}.csv",
            "mime_type": "text/csv",
            "content": csv_content,
            "row_count": len(row_data),
        }
    except (json.JSONDecodeError, csv.Error) as exc:
        return {"error": f"CSV generation failed: {exc}"}
```

**This is the Artifact pattern.** Walk through it carefully:

**Step 1 — Column parsing** (line 132):

```python
col_list = [c.strip() for c in columns.split(",")]
```

The `columns` parameter is a comma-separated string like `"Name,Age,Score"`.
The `.strip()` handles whitespace around column names (e.g., `"Name, Age,
Score"` works correctly).

**Step 2 — Row parsing** (line 133):

```python
row_data: list[list] = json.loads(rows_json)
```

The `rows_json` parameter is a JSON-encoded list of lists, e.g.,
`'[["Alice", 30, 95], ["Bob", 25, 87]]'`. Each inner list is one row.

**Step 3 — CSV generation** (lines 135–140):

```python
output = io.StringIO()
writer = csv.writer(output)
writer.writerow(col_list)
for row in row_data:
    writer.writerow(row)
csv_content = output.getvalue()
```

Standard `csv.writer` pattern. Writes to an in-memory buffer, then extracts
the CSV string. The `csv` module handles quoting, escaping, and newlines
correctly — no manual string concatenation.

**Step 4 — Filename sanitization** (line 142):

```python
safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)
```

The LLM-provided title might contain characters unsafe for filenames (spaces,
slashes, special characters). This replaces anything that is not alphanumeric,
hyphen, or underscore with an underscore.

**Step 5 — Artifact payload** (lines 144–149):

```python
return {
    "filename": f"{safe_title}.csv",
    "mime_type": "text/csv",
    "content": csv_content,
    "row_count": len(row_data),
}
```

**This is the key teaching point.** The function does **not** call any ADK
Artifact API. It simply returns a dict with the right keys. The ADK agent
framework recognizes this pattern — a dict with `content` and `mime_type` —
and attaches it to the A2A response as a `FilePart` Artifact.

**Explain the separation of concerns:**

- The **tool** is responsible for generating the content and metadata.
- The **framework** is responsible for packaging it as an A2A Artifact.
- The **tool never imports ADK**. It is pure business logic.

**Note the TODO on line 130**: `# TODO: Use ADK artifact service to persist
the file and return an Artifact ID`. In a production system, you would save
the file to Cloud Storage or an artifact service and return a persistent URL
or ID. The current implementation returns the content inline, which works for
small files but does not scale to large datasets.

---

## Design Patterns to Highlight

1. **Function Tool Contract**: Every tool returns a `dict`. On success, the
   dict contains the result data. On failure, the dict contains an `error`
   key. ADK serializes the dict as JSON and passes it back to the LLM. The
   LLM reads the result and formulates a natural language response. This
   is the universal ADK function tool pattern — no special return types, no
   framework-specific wrappers.

2. **Artifact Pattern**: A tool returns structured metadata (`filename`,
   `mime_type`, `content`) that the framework promotes to a `FilePart`
   Artifact. The tool itself has no knowledge of the A2A protocol — it just
   returns a dict. This clean separation means the tool is reusable outside
   of ADK.

3. **Defensive Parsing**: Every function wraps its logic in `try/except`
   and returns error dicts instead of raising exceptions. This ensures the
   LLM always gets a usable response, even when the input is malformed. The
   LLM can then report the error to the user in natural language rather
   than crashing.

4. **Convention Over Configuration**: Delimiter auto-detection, flexible
   input formats (flat list or object list), and title sanitization all
   reduce the burden on the LLM. The fewer decisions the LLM needs to make,
   the more reliable the agent becomes.

5. **Standard Library Only**: Zero external dependencies. The tools use
   `csv`, `io`, `json`, and `statistics` — all from Python's standard
   library. This makes the tools easy to test, deploy, and maintain. No
   version conflicts, no security advisories from third-party packages.

---

## Common Student Questions

1. **"Why does `compute_statistics` take a JSON string instead of a Python
   list?"** Because LLM tool calls pass arguments as serialized values.
   When the model calls `compute_statistics(data="[1, 2, 3]")`, the `data`
   parameter arrives as a string. The function must deserialize it with
   `json.loads()`. This is an LLM tool calling convention, not a design
   choice.

2. **"Why not use pandas for CSV parsing and statistics?"** Pandas is a
   heavy dependency (~30 MB). For a demo that parses small CSV files and
   computes basic statistics, the standard library is sufficient. In a
   production data agent handling large datasets, pandas (or polars) would
   be the right choice.

3. **"How does the Artifact actually get to the client?"** The tool returns
   the dict with `content`, `mime_type`, and `filename`. ADK sees this
   pattern and wraps it in an A2A `FilePart` in the response message. The
   client receives it as part of the A2A response and can extract the file.
   The tool itself does not handle A2A protocol details.

4. **"What if the CSV data is too large to return inline?"** The current
   implementation returns the full CSV content as a string in the response.
   For large datasets, you would instead write the file to Cloud Storage,
   return a signed URL, and have the client download it separately. The TODO
   comment on line 130 notes this limitation.

5. **"Why does `_detect_delimiter` only check the first line?"** The
   header row is the most reliable indicator of the delimiter. Data rows
   might contain the delimiter character inside quoted fields (e.g.,
   `"Smith, John"` in a comma-delimited file), which would confuse
   multi-line analysis. Checking only the header is a pragmatic heuristic.

6. **"Why is `stdev` guarded for single-element lists but `mean` and
   `median` are not?"** `statistics.mean()` and `statistics.median()` work
   with a single element (returning that element). `statistics.stdev()`
   divides by `n-1` (sample standard deviation), which is undefined for
   `n=1`. This is a mathematical constraint, not a Python limitation.

---

## Related Files

- `data_agent/agent.py` — Registers these functions as tools in the
  `LlmAgent` via `tools=[generate_csv_report, parse_csv_data, compute_statistics]`
- `shared/callbacks.py` — `logging_callback_before_tool` and
  `logging_callback_after_tool` log every call to these functions (if wired in)
- `tests/` — Unit tests that call these functions directly with various
  inputs (valid CSV, malformed CSV, empty data, single-element lists)
- `shared/config.py` — No direct dependency, but the agent that calls these
  tools reads its model configuration from settings
