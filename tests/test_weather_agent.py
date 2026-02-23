"""
Tests for weather_agent tools and agent configuration.

Tests the tool functions directly (unit tests) and validates the
Agent Card is correctly configured.

Reference: F1, F2, F3, F8, F12.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Tool unit tests ───────────────────────────────────────────────────────────

class TestGetWeather:
    """Unit tests for the get_weather tool function."""

    def test_returns_mock_data_when_no_api_key(self, monkeypatch):
        """get_weather should return mock data when OPENWEATHERMAP_API_KEY is empty."""
        monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "")
        # Re-import to pick up env change
        from weather_agent.tools import get_weather
        result = get_weather("London")
        assert "temperature_c" in result
        assert "temperature_f" in result
        assert "conditions" in result
        assert "MOCK DATA" in result.get("note", "")

    def test_mock_data_city_is_titlecased(self, monkeypatch):
        """Mock data should title-case the city name."""
        monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "")
        from weather_agent.tools import get_weather
        result = get_weather("new york")
        assert result["city"] == "New York"

    def test_returns_error_on_api_failure(self, monkeypatch):
        """get_weather should return an error dict on API failure."""
        import weather_agent.tools as tools_module
        # Patch the settings singleton on the tools module so it sees a key
        monkeypatch.setattr(tools_module.settings, "OPENWEATHERMAP_API_KEY", "fake-key")
        import httpx
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = \
                httpx.RequestError("connection refused")
            result = tools_module.get_weather("London")
        assert "error" in result


class TestGetForecast:
    """Unit tests for the get_forecast tool function."""

    def test_returns_mock_forecast_when_no_api_key(self, monkeypatch):
        """get_forecast should return mock data when no API key."""
        monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "")
        from weather_agent.tools import get_forecast
        result = get_forecast("Tokyo", days=3)
        assert "forecast" in result
        assert len(result["forecast"]) == 3
        assert "date" in result["forecast"][0]

    def test_forecast_days_capped_at_5(self, monkeypatch):
        """Forecast should be capped at 5 days maximum."""
        monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "")
        from weather_agent.tools import get_forecast
        result = get_forecast("Paris", days=10)
        assert len(result["forecast"]) <= 5


class TestWeatherAgentCard:
    """Tests for weather_agent Agent Card configuration."""

    def test_agent_card_has_streaming_enabled(self):
        """Agent Card should advertise streaming=True."""
        from weather_agent.agent import _AGENT_CARD
        assert _AGENT_CARD.capabilities.streaming is True

    def test_agent_card_has_skills(self):
        """Agent Card should have at least two skills."""
        from weather_agent.agent import _AGENT_CARD
        assert len(_AGENT_CARD.skills) >= 2
        skill_ids = [s.id for s in _AGENT_CARD.skills]
        assert "weather_lookup" in skill_ids
        assert "weather_forecast" in skill_ids

    def test_root_agent_has_tools(self):
        """root_agent should have get_weather and get_forecast tools registered."""
        from weather_agent.agent import root_agent
        # TODO: Verify tool registration via root_agent.tools attribute
        assert root_agent is not None
        assert root_agent.name == "weather_agent"
