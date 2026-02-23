"""
Extended tests for shared/callbacks.py — logging callbacks (pass-through
verification), all guardrail patterns, and cache edge cases.

Reference: F16 — Callbacks; F17 — Safety & Guardrails.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ── Logging callbacks — pass-through verification ─────────────────────────────


class TestLoggingCallbacksPassThrough:
    """All logging callbacks must return None (pass-through, not intercept)."""

    def test_before_model_returns_none(self):
        from shared.callbacks import logging_callback_before_model
        ctx = MagicMock()
        ctx.agent_name = "test_agent"
        req = MagicMock()
        req.contents = []
        result = logging_callback_before_model(ctx, req)
        assert result is None

    def test_after_model_returns_none(self):
        from shared.callbacks import logging_callback_after_model
        ctx = MagicMock()
        ctx.agent_name = "test_agent"
        resp = MagicMock()
        resp.usage_metadata = None
        result = logging_callback_after_model(ctx, resp)
        assert result is None

    def test_before_tool_returns_none(self):
        from shared.callbacks import logging_callback_before_tool
        tool = MagicMock()
        tool.name = "get_weather"
        result = logging_callback_before_tool(tool, {"city": "London"}, None)
        assert result is None

    def test_after_tool_returns_none(self):
        from shared.callbacks import logging_callback_after_tool
        tool = MagicMock()
        tool.name = "get_weather"
        result = logging_callback_after_tool(tool, {"city": "London"}, None, {"temp": 20})
        assert result is None

    def test_before_model_handles_missing_agent_name(self):
        """Callback must not crash if agent_name is absent from context."""
        from shared.callbacks import logging_callback_before_model
        ctx = MagicMock(spec=[])  # no attributes allowed
        req = MagicMock()
        result = logging_callback_before_model(ctx, req)
        assert result is None

    def test_after_model_with_token_metadata_returns_none(self):
        """Token count logging should not intercept the response."""
        from shared.callbacks import logging_callback_after_model
        ctx = MagicMock()
        usage = MagicMock()
        usage.prompt_token_count = 100
        usage.candidates_token_count = 50
        usage.total_token_count = 150
        resp = MagicMock()
        resp.usage_metadata = usage
        result = logging_callback_after_model(ctx, resp)
        assert result is None

    def test_after_model_with_none_metadata_does_not_crash(self):
        from shared.callbacks import logging_callback_after_model
        ctx = MagicMock()
        resp = MagicMock()
        resp.usage_metadata = None
        # Must not raise
        logging_callback_after_model(ctx, resp)

    def test_after_tool_with_non_dict_response_does_not_crash(self):
        """Tool response may not always be a dict — callback must be robust."""
        from shared.callbacks import logging_callback_after_tool
        tool = MagicMock()
        tool.name = "some_tool"
        result = logging_callback_after_tool(tool, {}, None, "not a dict")
        assert result is None


# ── Guardrail callback — complete pattern coverage ───────────────────────────


class TestGuardrailAllPatterns:
    """Every pattern in _DANGEROUS_PATTERNS must be blocked."""

    def _call_guardrail(self, code: str) -> dict | None:
        from shared.callbacks import guardrail_callback_before_tool
        tool = MagicMock()
        tool.name = "code_tool"
        return guardrail_callback_before_tool(tool, {"code": code}, None)

    def test_blocks_os_system(self):
        result = self._call_guardrail("os.system('rm -rf /')")
        assert result is not None
        assert "error" in result

    def test_blocks_subprocess(self):
        result = self._call_guardrail("import subprocess; subprocess.run(['ls'])")
        assert result is not None
        assert "error" in result

    def test_blocks_shutil_rmtree(self):
        result = self._call_guardrail("shutil.rmtree('/important/dir')")
        assert result is not None
        assert "error" in result

    def test_blocks_dunder_import(self):
        result = self._call_guardrail("__import__('os').system('id')")
        assert result is not None
        assert "error" in result

    def test_blocks_exec(self):
        result = self._call_guardrail("exec('malicious_code()')")
        assert result is not None
        assert "error" in result

    def test_blocks_eval(self):
        result = self._call_guardrail("eval(user_input)")
        assert result is not None
        assert "error" in result

    def test_blocks_open_function(self):
        result = self._call_guardrail("with open('/etc/passwd') as f: data = f.read()")
        assert result is not None
        assert "error" in result

    def test_allows_safe_print_code(self):
        result = self._call_guardrail("print('hello world')")
        assert result is None

    def test_allows_math_computation(self):
        result = self._call_guardrail("result = sum([1, 2, 3, 4, 5])")
        assert result is None

    def test_allows_list_comprehension(self):
        result = self._call_guardrail("evens = [x for x in range(10) if x % 2 == 0]")
        assert result is None

    def test_allows_import_math(self):
        result = self._call_guardrail("import math\nprint(math.pi)")
        assert result is None

    def test_error_message_names_the_blocked_pattern(self):
        result = self._call_guardrail("os.system('cmd')")
        assert "os.system" in result["error"]

    def test_blocks_on_pattern_embedded_in_longer_code(self):
        """Pattern detection should work even when embedded mid-code."""
        result = self._call_guardrail("x = 1\nif x > 0:\n    os.system('id')\nprint(x)")
        assert result is not None

    def test_empty_code_string_is_allowed(self):
        result = self._call_guardrail("")
        assert result is None

    def test_no_code_argument_is_allowed(self):
        from shared.callbacks import guardrail_callback_before_tool
        tool = MagicMock()
        tool.name = "get_weather"
        result = guardrail_callback_before_tool(tool, {"city": "London"}, None)
        assert result is None


# ── Cache callbacks — extended edge cases ─────────────────────────────────────


class TestCacheCallbacksExtended:
    """Extended tests for cache miss/hit behaviour and isolation by tool/args."""

    def test_cache_miss_for_new_tool(self):
        from shared.callbacks import cache_callback_before_tool, _tool_cache
        _tool_cache.clear()
        tool = MagicMock()
        tool.name = "brand_new_tool"
        result = cache_callback_before_tool(tool, {"arg": "val"}, None)
        assert result is None

    def test_cache_hit_returns_stored_value(self):
        from shared.callbacks import (
            cache_callback_before_tool,
            cache_callback_after_tool,
            _tool_cache,
        )
        _tool_cache.clear()
        tool = MagicMock()
        tool.name = "get_weather"
        args = {"city": "Berlin"}
        response = {"temperature_c": 15.0, "conditions": "Cloudy"}

        cache_callback_after_tool(tool, args, None, response)
        result = cache_callback_before_tool(tool, args, None)
        assert result == response

    def test_cache_is_keyed_by_tool_name_and_args(self):
        from shared.callbacks import (
            cache_callback_before_tool,
            cache_callback_after_tool,
            _tool_cache,
        )
        _tool_cache.clear()
        tool_a = MagicMock()
        tool_a.name = "get_weather"
        tool_b = MagicMock()
        tool_b.name = "get_forecast"
        args = {"city": "London"}

        # Store only for tool_a
        cache_callback_after_tool(tool_a, args, None, {"temp": 20})

        # tool_b with same args must be a cache miss
        result = cache_callback_before_tool(tool_b, args, None)
        assert result is None

    def test_different_args_have_separate_cache_entries(self):
        from shared.callbacks import (
            cache_callback_before_tool,
            cache_callback_after_tool,
            _tool_cache,
        )
        _tool_cache.clear()
        tool = MagicMock()
        tool.name = "get_weather"

        cache_callback_after_tool(tool, {"city": "Paris"}, None, {"temp": 22})
        cache_callback_after_tool(tool, {"city": "London"}, None, {"temp": 15})

        paris = cache_callback_before_tool(tool, {"city": "Paris"}, None)
        london = cache_callback_before_tool(tool, {"city": "London"}, None)

        assert paris["temp"] == 22
        assert london["temp"] == 15

    def test_cache_after_tool_returns_none(self):
        from shared.callbacks import cache_callback_after_tool
        tool = MagicMock()
        tool.name = "t"
        result = cache_callback_after_tool(tool, {"k": "v"}, None, {"r": 1})
        assert result is None

    def test_cache_handles_non_hashable_args_gracefully(self):
        """Non-hashable args (e.g. list values) must not raise."""
        from shared.callbacks import cache_callback_before_tool, cache_callback_after_tool
        tool = MagicMock()
        tool.name = "some_tool"
        args = {"data": [1, 2, 3]}  # list is not hashable, but dict key is fine

        # These must not raise even if caching is skipped
        cache_callback_before_tool(tool, args, None)
        cache_callback_after_tool(tool, args, None, {"result": "ok"})

    def test_cache_miss_after_clear(self):
        from shared.callbacks import (
            cache_callback_before_tool,
            cache_callback_after_tool,
            _tool_cache,
        )
        _tool_cache.clear()
        tool = MagicMock()
        tool.name = "get_weather"
        args = {"city": "Rome"}

        # Store
        cache_callback_after_tool(tool, args, None, {"temp": 25})
        # Hit
        assert cache_callback_before_tool(tool, args, None) is not None

        # Clear and check miss
        _tool_cache.clear()
        assert cache_callback_before_tool(tool, args, None) is None
