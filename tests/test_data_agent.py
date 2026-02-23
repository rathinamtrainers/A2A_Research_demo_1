"""
Tests for data_agent tools (CSV parsing, statistics, report generation).

Reference: F12, F15.
"""

from __future__ import annotations

import json

import pytest


class TestParseCsvData:
    """Tests for the parse_csv_data tool."""

    def test_parses_simple_csv(self):
        from data_agent.tools import parse_csv_data
        csv = "name,age,score\nAlice,30,95\nBob,25,88"
        result = parse_csv_data(csv)
        assert result["row_count"] == 2
        assert result["columns"] == ["name", "age", "score"]
        assert result["rows"][0]["name"] == "Alice"

    def test_returns_error_on_empty_input(self):
        from data_agent.tools import parse_csv_data
        result = parse_csv_data("")
        # Empty input should either return empty rows or an error
        assert "row_count" in result or "error" in result

    def test_parses_single_column(self):
        from data_agent.tools import parse_csv_data
        csv = "value\n1\n2\n3"
        result = parse_csv_data(csv)
        assert result["row_count"] == 3
        assert result["columns"] == ["value"]


class TestComputeStatistics:
    """Tests for the compute_statistics tool."""

    def test_computes_basic_stats_on_list(self):
        from data_agent.tools import compute_statistics
        data = json.dumps([1, 2, 3, 4, 5])
        result = compute_statistics(data)
        assert result["count"] == 5
        assert result["mean"] == 3.0
        assert result["min"] == 1
        assert result["max"] == 5

    def test_handles_single_value(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps([42]))
        assert result["count"] == 1
        assert result["mean"] == 42.0
        assert result["stdev"] == 0.0

    def test_returns_error_on_invalid_json(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics("not-json")
        assert "error" in result

    def test_computes_stats_on_dict_list(self):
        from data_agent.tools import compute_statistics
        data = json.dumps([{"value": 10}, {"value": 20}, {"value": 30}])
        result = compute_statistics(data)
        assert result["count"] == 3
        assert result["mean"] == 20.0


class TestGenerateCsvReport:
    """Tests for the generate_csv_report tool."""

    def test_generates_valid_csv(self):
        from data_agent.tools import generate_csv_report
        rows = [["Alice", 30, 95], ["Bob", 25, 88]]
        result = generate_csv_report(
            title="Test Report",
            columns="Name,Age,Score",
            rows_json=json.dumps(rows),
        )
        assert result["mime_type"] == "text/csv"
        assert "Name,Age,Score" in result["content"]
        assert "Alice" in result["content"]
        assert result["row_count"] == 2

    def test_filename_has_csv_extension(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report(
            title="My Report",
            columns="A,B",
            rows_json=json.dumps([[1, 2]]),
        )
        assert result["filename"].endswith(".csv")

    def test_returns_error_on_invalid_rows_json(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report(
            title="Bad",
            columns="A,B",
            rows_json="not valid json",
        )
        assert "error" in result
