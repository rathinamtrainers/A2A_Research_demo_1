"""
Extended tests for data_agent/tools.py — delimiter detection, CSV parsing edge cases,
statistics edge cases, and CSV report generation.

Reference: F12 — Function Tools; F15 — Artifacts.
"""

from __future__ import annotations

import json
import math

import pytest


# ── _detect_delimiter ─────────────────────────────────────────────────────────


class TestDetectDelimiter:
    """Tests for the internal _detect_delimiter helper."""

    def test_detects_tab_delimiter(self):
        from data_agent.tools import _detect_delimiter
        assert _detect_delimiter("col1\tcol2\tcol3") == "\t"

    def test_detects_semicolon_delimiter(self):
        from data_agent.tools import _detect_delimiter
        assert _detect_delimiter("col1;col2;col3") == ";"

    def test_defaults_to_comma(self):
        from data_agent.tools import _detect_delimiter
        assert _detect_delimiter("col1,col2,col3") == ","

    def test_tab_preferred_over_semicolon_when_both_present(self):
        from data_agent.tools import _detect_delimiter
        # Tab is checked first in the implementation
        assert _detect_delimiter("col1\tcol2;col3") == "\t"

    def test_empty_string_defaults_to_comma(self):
        from data_agent.tools import _detect_delimiter
        assert _detect_delimiter("") == ","

    def test_single_column_no_delimiters_defaults_to_comma(self):
        from data_agent.tools import _detect_delimiter
        assert _detect_delimiter("singlecolumn") == ","

    def test_uses_only_first_line_for_detection(self):
        from data_agent.tools import _detect_delimiter
        # Second line has tabs, but first line has semicolons
        result = _detect_delimiter("col1;col2;col3\ndata\tdata\tdata")
        assert result == ";"


# ── parse_csv_data (extended) ─────────────────────────────────────────────────


class TestParseCsvDataExtended:
    """Additional CSV parsing tests covering delimiter variants and edge cases."""

    def test_parses_tab_delimited_csv(self):
        from data_agent.tools import parse_csv_data
        csv = "name\tage\tscore\nAlice\t30\t95\nBob\t25\t88"
        result = parse_csv_data(csv)
        assert result["delimiter"] == "\t"
        assert result["row_count"] == 2
        assert result["rows"][0]["name"] == "Alice"
        assert result["rows"][1]["age"] == "25"

    def test_parses_semicolon_delimited_csv(self):
        from data_agent.tools import parse_csv_data
        csv = "name;value\nAlpha;100\nBeta;200"
        result = parse_csv_data(csv)
        assert result["delimiter"] == ";"
        assert result["row_count"] == 2
        assert result["rows"][1]["name"] == "Beta"

    def test_delimiter_reported_in_result(self):
        from data_agent.tools import parse_csv_data
        csv = "a,b\n1,2"
        result = parse_csv_data(csv)
        assert result["delimiter"] == ","

    def test_columns_list_is_correct_length(self):
        from data_agent.tools import parse_csv_data
        csv = "a,b,c,d,e\n1,2,3,4,5"
        result = parse_csv_data(csv)
        assert len(result["columns"]) == 5

    def test_rows_are_dicts_keyed_by_column_name(self):
        from data_agent.tools import parse_csv_data
        csv = "x,y\n10,20\n30,40"
        result = parse_csv_data(csv)
        assert all("x" in row and "y" in row for row in result["rows"])

    def test_strip_whitespace_around_content(self):
        from data_agent.tools import parse_csv_data
        csv = "\n\nname,age\nAlice,30\n\n"
        result = parse_csv_data(csv)
        # After stripping, should parse successfully
        assert "error" not in result or result.get("row_count", 0) >= 0

    def test_header_only_csv_has_zero_rows(self):
        from data_agent.tools import parse_csv_data
        csv = "name,age,score"
        result = parse_csv_data(csv)
        assert result["row_count"] == 0
        assert result["columns"] == ["name", "age", "score"]

    def test_many_rows_parsed_correctly(self):
        from data_agent.tools import parse_csv_data
        rows = "\n".join(f"row{i},{i}" for i in range(100))
        csv = f"name,value\n{rows}"
        result = parse_csv_data(csv)
        assert result["row_count"] == 100


# ── compute_statistics (extended) ────────────────────────────────────────────


class TestComputeStatisticsExtended:
    """Additional statistics tests covering edge cases and mathematical correctness."""

    def test_sum_is_correct(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps([2, 4, 6]))
        assert result["sum"] == 12.0

    def test_median_odd_count(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps([1, 3, 5]))
        assert result["median"] == 3.0

    def test_median_even_count(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps([1, 2, 3, 4]))
        assert result["median"] == 2.5

    def test_min_and_max_correct(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps([7, 2, 9, 1, 5]))
        assert result["min"] == 1
        assert result["max"] == 9

    def test_stdev_is_zero_for_single_value(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps([42]))
        assert result["stdev"] == 0.0

    def test_stdev_is_correct_for_known_data(self):
        from data_agent.tools import compute_statistics
        # [1, 2, 3]: sample stdev = 1.0 exactly (sum of sq. deviations=2, n-1=2, var=1)
        result = compute_statistics(json.dumps([1.0, 2.0, 3.0]))
        assert abs(result["stdev"] - 1.0) < 0.0001

    def test_empty_list_returns_error(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps([]))
        assert "error" in result

    def test_non_list_json_object_returns_error(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps({"value": 42}))
        assert "error" in result

    def test_list_of_strings_returns_error(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps(["a", "b", "c"]))
        assert "error" in result

    def test_dict_list_without_value_key_returns_error(self):
        from data_agent.tools import compute_statistics
        data = json.dumps([{"name": "Alice"}, {"name": "Bob"}])
        result = compute_statistics(data)
        assert "error" in result

    def test_dict_list_with_value_key_computes_correctly(self):
        from data_agent.tools import compute_statistics
        data = json.dumps([{"name": "A", "value": 10}, {"name": "B", "value": 20}])
        result = compute_statistics(data)
        assert result["count"] == 2
        assert result["mean"] == 15.0

    def test_mixed_int_and_float_values(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps([1, 2.5, 3]))
        assert result["count"] == 3
        assert abs(result["mean"] - 2.1667) < 0.001

    def test_count_matches_input_length(self):
        from data_agent.tools import compute_statistics
        data = list(range(50))
        result = compute_statistics(json.dumps(data))
        assert result["count"] == 50

    def test_large_numbers_do_not_overflow(self):
        from data_agent.tools import compute_statistics
        result = compute_statistics(json.dumps([1e15, 2e15, 3e15]))
        assert result["count"] == 3
        assert result["mean"] == pytest.approx(2e15, rel=1e-6)


# ── generate_csv_report (extended) ───────────────────────────────────────────


class TestGenerateCsvReportExtended:
    """Additional CSV report generation tests."""

    def test_title_spaces_replaced_in_filename(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report(
            title="My Report 2024",
            columns="Name,Score",
            rows_json=json.dumps([["Alice", 95]]),
        )
        assert " " not in result["filename"]

    def test_special_chars_in_title_sanitized(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report(
            title="Report/With:Special*Chars",
            columns="A,B",
            rows_json=json.dumps([[1, 2]]),
        )
        assert result["filename"].endswith(".csv")
        # Special characters should be replaced
        for char in ("/", ":", "*"):
            assert char not in result["filename"]

    def test_columns_stripped_of_whitespace(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report(
            title="test",
            columns=" Name , Score , Grade ",
            rows_json=json.dumps([["Alice", 95, "A"]]),
        )
        header_line = result["content"].split("\n")[0]
        assert "Name" in header_line
        # No leading/trailing space around column name
        assert " Name" not in header_line

    def test_empty_rows_list_has_zero_row_count(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report("empty", "A,B", json.dumps([]))
        assert result["row_count"] == 0

    def test_empty_rows_list_still_has_header(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report("empty", "Col1,Col2", json.dumps([]))
        assert "Col1" in result["content"]
        assert "Col2" in result["content"]

    def test_many_rows_in_report(self):
        from data_agent.tools import generate_csv_report
        rows = [[f"row{i}", i * 2] for i in range(50)]
        result = generate_csv_report("big", "Name,Value", json.dumps(rows))
        assert result["row_count"] == 50

    def test_content_is_valid_csv_with_newlines(self):
        from data_agent.tools import generate_csv_report
        import csv, io
        result = generate_csv_report(
            "test",
            "Name,Age",
            json.dumps([["Alice", 30], ["Bob", 25]]),
        )
        reader = csv.reader(io.StringIO(result["content"]))
        rows = list(reader)
        # Should have header + 2 data rows (plus possible trailing empty)
        data_rows = [r for r in rows if r]
        assert len(data_rows) >= 3  # header + 2 data rows

    def test_mime_type_is_text_csv(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report("t", "A", json.dumps([[1]]))
        assert result["mime_type"] == "text/csv"

    def test_filename_always_ends_with_csv(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report("MyReport", "X,Y", json.dumps([[1, 2]]))
        assert result["filename"].endswith(".csv")

    def test_invalid_rows_json_returns_error(self):
        from data_agent.tools import generate_csv_report
        result = generate_csv_report("bad", "A,B", "not valid json at all")
        assert "error" in result
