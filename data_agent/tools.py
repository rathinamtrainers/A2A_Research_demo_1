"""
Data processing tools for the Data Agent.

All tools return standard Python dicts so ADK can serialise them as
JSON in the model's context.  The ``generate_csv_report`` tool also
demonstrates the pattern for returning file content that the agent
framework can expose as an A2A Artifact.

Reference: F12 — Function Tools; F15 — Artifacts.
"""

from __future__ import annotations

import csv
import io
import json
import statistics
from typing import Any


def _detect_delimiter(csv_text: str) -> str:
    """
    Auto-detect the CSV delimiter from the first line of text.

    Checks for tab (``\\t``), semicolon (``;``), and comma (``,``) in order
    and returns the first one found in the header row.  Falls back to comma.

    Args:
        csv_text: Raw CSV text.

    Returns:
        The detected delimiter character.
    """
    first_line = csv_text.split("\n")[0] if csv_text else ""
    if "\t" in first_line:
        return "\t"
    if ";" in first_line:
        return ";"
    return ","


def parse_csv_data(csv_text: str) -> dict:
    """
    Parse a CSV-formatted string into a structured representation.

    Automatically detects the delimiter (comma, tab, semicolon) from the
    first line of the input, then parses all rows.

    Args:
        csv_text: Raw CSV text with a header row and data rows.

    Returns:
        A dict with ``columns`` (list of column names), ``rows`` (list
        of dicts mapping column→value), ``row_count`` (int), and
        ``delimiter`` (the auto-detected delimiter character).
        On error returns a dict with ``error`` key.
    """
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


def compute_statistics(data: str) -> dict:
    """
    Compute descriptive statistics on a JSON-encoded list of numbers
    or a JSON array of objects with a specified numeric column.

    Args:
        data: JSON string. Either:
              - A list of numbers: ``[1, 2, 3, 4, 5]``
              - A list of dicts with a ``value`` key: ``[{"name": "A", "value": 10}, ...]``

    Returns:
        A dict with ``count``, ``mean``, ``median``, ``stdev``,
        ``min``, ``max``, and ``sum``.  Returns ``{"error": ...}`` on failure.
    """
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


def generate_csv_report(title: str, columns: str, rows_json: str) -> dict:
    """
    Generate a CSV report and return its content as a string Artifact payload.

    The returned dict contains the CSV content as a string.  The ADK agent
    framework will attach this to the A2A response as a ``FilePart`` Artifact
    with ``mimeType: text/csv``.

    Args:
        title: Report title (used as the filename stem).
        columns: Comma-separated column header names, e.g. ``"Name,Age,Score"``.
        rows_json: JSON-encoded list of row lists, e.g. ``[["Alice",30,95], ...]``.

    Returns:
        A dict with ``filename``, ``mime_type``, ``content`` (CSV string),
        and ``row_count``.  Returns ``{"error": ...}`` on failure.
    """
    # TODO: Use ADK artifact service to persist the file and return an Artifact ID
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
