"""
Tests for shared callback functions.

Reference: F16 — Callbacks; F17 — Safety & Guardrails.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestGuardrailCallback:
    """Tests for guardrail_callback_before_tool."""

    def test_blocks_os_system(self):
        from shared.callbacks import guardrail_callback_before_tool
        tool = MagicMock(name="code_tool")
        result = guardrail_callback_before_tool(tool, {"code": "os.system('rm -rf /')"}, None)
        assert result is not None
        assert "error" in result
        assert "os.system" in result["error"]

    def test_blocks_subprocess(self):
        from shared.callbacks import guardrail_callback_before_tool
        tool = MagicMock(name="code_tool")
        result = guardrail_callback_before_tool(tool, {"code": "import subprocess; subprocess.run(['ls'])"}, None)
        assert result is not None
        assert "error" in result

    def test_allows_safe_code(self):
        from shared.callbacks import guardrail_callback_before_tool
        tool = MagicMock(name="code_tool")
        result = guardrail_callback_before_tool(tool, {"code": "print('hello world')"}, None)
        assert result is None  # No block

    def test_allows_non_code_tool(self):
        from shared.callbacks import guardrail_callback_before_tool
        tool = MagicMock(name="get_weather")
        result = guardrail_callback_before_tool(tool, {"city": "London"}, None)
        assert result is None

    def test_blocks_eval(self):
        from shared.callbacks import guardrail_callback_before_tool
        tool = MagicMock(name="code_tool")
        result = guardrail_callback_before_tool(tool, {"code": "eval(user_input)"}, None)
        assert result is not None


class TestCacheCallbacks:
    """Tests for cache callbacks."""

    def test_cache_miss_returns_none(self):
        from shared.callbacks import cache_callback_before_tool, _tool_cache
        _tool_cache.clear()
        tool = MagicMock(name="get_weather")
        result = cache_callback_before_tool(tool, {"city": "Paris"}, None)
        assert result is None  # Cache miss

    def test_cache_hit_returns_cached(self):
        from shared.callbacks import (
            cache_callback_after_tool,
            cache_callback_before_tool,
            _tool_cache,
        )
        _tool_cache.clear()
        tool = MagicMock(name="get_weather")
        tool_args = {"city": "Berlin"}
        response = {"temperature_c": 15.0, "conditions": "Cloudy"}

        # Store in cache
        cache_callback_after_tool(tool, tool_args, None, response)

        # Should hit on next call
        cached = cache_callback_before_tool(tool, tool_args, None)
        assert cached == response
