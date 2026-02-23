"""
Tests for orchestrator_agent/callbacks.py — URL redaction and safety prefix injection.

Reference: F16 — Callbacks; F17 — Safety & Guardrails.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orchestrator_agent.callbacks import (
    _REDACTED_PATTERNS,
    _SAFETY_MARKER,
    _SAFETY_PREFIX,
    orchestrator_after_model,
    orchestrator_before_model,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_response(text: str):
    """Build a mock LlmResponse containing a single text part."""
    part = MagicMock()
    part.text = text
    content = MagicMock()
    content.parts = [part]
    response = MagicMock()
    response.content = content
    return response, part


def _make_request_with_string_instruction(instruction: str):
    """Build a mock LlmRequest with a plain string system_instruction."""
    request = MagicMock()
    request.system_instruction = instruction
    return request


# ── orchestrator_after_model — URL redaction ─────────────────────────────────


class TestUrlRedaction:
    """orchestrator_after_model redacts internal URLs from model responses."""

    def test_redacts_localhost_in_url(self):
        response, part = _make_response("See http://localhost:8001/api for details.")
        orchestrator_after_model(MagicMock(), response)
        assert "localhost" not in part.text
        assert "[REDACTED]" in part.text

    def test_redacts_bare_localhost_word(self):
        response, part = _make_response("Connect to localhost port 8001.")
        orchestrator_after_model(MagicMock(), response)
        assert "localhost" not in part.text

    def test_redacts_127_0_0_1_in_url(self):
        response, part = _make_response("URL is http://127.0.0.1:8080/path.")
        orchestrator_after_model(MagicMock(), response)
        assert "127.0.0.1" not in part.text
        assert "[REDACTED]" in part.text

    def test_redacts_bare_127_0_0_1(self):
        response, part = _make_response("Address: 127.0.0.1")
        orchestrator_after_model(MagicMock(), response)
        assert "127.0.0.1" not in part.text

    def test_redacts_internal_prefix_pattern(self):
        response, part = _make_response("Call internal-agent.corp.net for info.")
        orchestrator_after_model(MagicMock(), response)
        assert "internal-" not in part.text

    def test_safe_text_is_unchanged(self):
        original = "The weather in London is 20°C and sunny today."
        response, part = _make_response(original)
        orchestrator_after_model(MagicMock(), response)
        assert part.text == original

    def test_redacts_multiple_patterns_in_same_text(self):
        response, part = _make_response(
            "Agents at http://localhost:8001 and http://127.0.0.1:8002."
        )
        orchestrator_after_model(MagicMock(), response)
        assert "localhost" not in part.text
        assert "127.0.0.1" not in part.text

    def test_returns_none(self):
        response, _ = _make_response("hello world")
        result = orchestrator_after_model(MagicMock(), response)
        assert result is None

    def test_handles_none_content_gracefully(self):
        response = MagicMock()
        response.content = None
        # Must not raise
        orchestrator_after_model(MagicMock(), response)

    def test_handles_empty_parts_list(self):
        content = MagicMock()
        content.parts = []
        response = MagicMock()
        response.content = content
        # Must not raise
        orchestrator_after_model(MagicMock(), response)

    def test_handles_part_with_none_text(self):
        part = MagicMock()
        part.text = None
        content = MagicMock()
        content.parts = [part]
        response = MagicMock()
        response.content = content
        # Must not raise
        orchestrator_after_model(MagicMock(), response)

    def test_multiple_parts_all_redacted(self):
        """All text parts in a response should have redaction applied."""
        part1 = MagicMock()
        part1.text = "Agent one is at localhost:8001"
        part2 = MagicMock()
        part2.text = "Agent two is at 127.0.0.1:8002"
        content = MagicMock()
        content.parts = [part1, part2]
        response = MagicMock()
        response.content = content

        orchestrator_after_model(MagicMock(), response)

        assert "localhost" not in part1.text
        assert "127.0.0.1" not in part2.text


# ── orchestrator_before_model — safety injection ─────────────────────────────


class TestSafetyPrefixInjection:
    """orchestrator_before_model injects safety prefix into system instructions."""

    def test_returns_none(self):
        request = MagicMock()
        request.system_instruction = None
        result = orchestrator_before_model(MagicMock(), request)
        assert result is None

    def test_injects_safety_prefix_into_string_instruction(self):
        request = _make_request_with_string_instruction("You are a helpful assistant.")
        orchestrator_before_model(MagicMock(), request)
        assert _SAFETY_MARKER in request.system_instruction
        assert request.system_instruction.startswith(_SAFETY_PREFIX)

    def test_does_not_double_inject_safety_prefix(self):
        """Safety prefix must be injected exactly once even if callback is called twice."""
        instruction = _SAFETY_PREFIX + "Be helpful and concise."
        request = _make_request_with_string_instruction(instruction)
        # Call twice
        orchestrator_before_model(MagicMock(), request)
        orchestrator_before_model(MagicMock(), request)
        count = request.system_instruction.count(_SAFETY_MARKER)
        assert count == 1

    def test_safety_prefix_prepended_before_existing_instruction(self):
        original = "You route requests to specialist agents."
        request = _make_request_with_string_instruction(original)
        orchestrator_before_model(MagicMock(), request)
        # Safety prefix should come before the original instruction
        idx_safety = request.system_instruction.index(_SAFETY_MARKER)
        idx_original = request.system_instruction.index("You route requests")
        assert idx_safety < idx_original

    def test_handles_none_system_instruction(self):
        request = MagicMock()
        request.system_instruction = None
        # Must not raise
        orchestrator_before_model(MagicMock(), request)

    def test_handles_missing_system_instruction_attribute(self):
        """If llm_request has no system_instruction, callback must not raise."""
        request = MagicMock(spec=[])  # no attributes allowed
        orchestrator_before_model(MagicMock(), request)

    def test_safety_prefix_content_is_meaningful(self):
        """The injected safety prefix should mention internal URLs and credentials."""
        request = _make_request_with_string_instruction("Be helpful.")
        orchestrator_before_model(MagicMock(), request)
        injected = request.system_instruction
        # At least one security-relevant keyword present
        assert any(kw in injected for kw in ["URL", "credential", "API key", "secret", "internal"])

    def test_callback_context_passed_to_logging(self):
        """Callback must not crash when callback_context is a minimal MagicMock."""
        ctx = MagicMock()
        ctx.agent_name = "orchestrator"
        request = _make_request_with_string_instruction("Be helpful.")
        orchestrator_before_model(ctx, request)
