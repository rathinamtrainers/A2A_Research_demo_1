"""
Extended tests for weather_agent/tools.py — forecast aggregation internals,
mock data field validation, and OWM API response parsing.

Reference: F12 — Function Tools; F1, F2 — Weather Agent.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ── _aggregate_forecast (internal aggregation logic) ─────────────────────────


class TestAggregateForecast:
    """Unit tests for the internal _aggregate_forecast helper."""

    def test_groups_slots_by_calendar_date(self):
        from weather_agent.tools import _aggregate_forecast
        slots = [
            {"dt_txt": "2024-06-01 06:00:00", "main": {"temp": 10.0}, "weather": [{"main": "Clear"}]},
            {"dt_txt": "2024-06-01 12:00:00", "main": {"temp": 18.0}, "weather": [{"main": "Clear"}]},
            {"dt_txt": "2024-06-02 06:00:00", "main": {"temp": 20.0}, "weather": [{"main": "Clouds"}]},
        ]
        result = _aggregate_forecast(slots, days=5)
        assert len(result) == 2
        dates = [r["date"] for r in result]
        assert "2024-06-01" in dates
        assert "2024-06-02" in dates

    def test_respects_days_cap(self):
        from weather_agent.tools import _aggregate_forecast
        slots = []
        for day in range(7):
            dt = f"2024-06-{10 + day:02d} 06:00:00"
            slots.append(
                {"dt_txt": dt, "main": {"temp": 15.0}, "weather": [{"main": "Clear"}]}
            )
        result = _aggregate_forecast(slots, days=3)
        assert len(result) == 3

    def test_computes_daily_high_temperature(self):
        from weather_agent.tools import _aggregate_forecast
        slots = [
            {"dt_txt": "2024-06-01 00:00:00", "main": {"temp": 5.0}, "weather": [{"main": "Clear"}]},
            {"dt_txt": "2024-06-01 12:00:00", "main": {"temp": 22.0}, "weather": [{"main": "Clear"}]},
            {"dt_txt": "2024-06-01 18:00:00", "main": {"temp": 18.0}, "weather": [{"main": "Clear"}]},
        ]
        result = _aggregate_forecast(slots, days=1)
        assert result[0]["high_c"] == 22.0

    def test_computes_daily_low_temperature(self):
        from weather_agent.tools import _aggregate_forecast
        slots = [
            {"dt_txt": "2024-06-01 03:00:00", "main": {"temp": 3.0}, "weather": [{"main": "Clear"}]},
            {"dt_txt": "2024-06-01 12:00:00", "main": {"temp": 20.0}, "weather": [{"main": "Clear"}]},
        ]
        result = _aggregate_forecast(slots, days=1)
        assert result[0]["low_c"] == 3.0

    def test_selects_most_frequent_condition_as_dominant(self):
        from weather_agent.tools import _aggregate_forecast
        slots = [
            {"dt_txt": "2024-06-01 00:00:00", "main": {"temp": 10.0}, "weather": [{"main": "Rain"}]},
            {"dt_txt": "2024-06-01 06:00:00", "main": {"temp": 11.0}, "weather": [{"main": "Clear"}]},
            {"dt_txt": "2024-06-01 12:00:00", "main": {"temp": 12.0}, "weather": [{"main": "Clear"}]},
            {"dt_txt": "2024-06-01 18:00:00", "main": {"temp": 13.0}, "weather": [{"main": "Clear"}]},
        ]
        result = _aggregate_forecast(slots, days=1)
        assert result[0]["conditions"] == "Clear"

    def test_empty_slots_returns_empty_list(self):
        from weather_agent.tools import _aggregate_forecast
        result = _aggregate_forecast([], days=5)
        assert result == []

    def test_result_sorted_by_date_ascending(self):
        from weather_agent.tools import _aggregate_forecast
        slots = [
            {"dt_txt": "2024-06-03 06:00:00", "main": {"temp": 15.0}, "weather": [{"main": "Clear"}]},
            {"dt_txt": "2024-06-01 06:00:00", "main": {"temp": 10.0}, "weather": [{"main": "Clear"}]},
            {"dt_txt": "2024-06-02 06:00:00", "main": {"temp": 12.0}, "weather": [{"main": "Clouds"}]},
        ]
        result = _aggregate_forecast(slots, days=3)
        dates = [r["date"] for r in result]
        assert dates == sorted(dates)

    def test_each_entry_has_required_keys(self):
        from weather_agent.tools import _aggregate_forecast
        slots = [
            {"dt_txt": "2024-06-01 06:00:00", "main": {"temp": 15.0}, "weather": [{"main": "Clear"}]},
        ]
        result = _aggregate_forecast(slots, days=1)
        assert len(result) == 1
        for key in ("date", "high_c", "low_c", "conditions"):
            assert key in result[0], f"Missing key: {key}"

    def test_temperatures_are_rounded(self):
        from weather_agent.tools import _aggregate_forecast
        slots = [
            {"dt_txt": "2024-06-01 06:00:00", "main": {"temp": 18.123456}, "weather": [{"main": "Clear"}]},
        ]
        result = _aggregate_forecast(slots, days=1)
        # Should be rounded to 1 decimal
        assert result[0]["high_c"] == 18.1


# ── Mock weather data validation ──────────────────────────────────────────────


class TestMockWeatherData:
    """Mock weather data returns all required fields with correct types."""

    @pytest.mark.asyncio
    async def test_all_required_fields_present(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_weather("London")
        required = [
            "city", "country", "temperature_c", "temperature_f",
            "feels_like_c", "humidity_percent", "wind_speed_ms",
            "conditions", "description",
        ]
        for field in required:
            assert field in result, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_temperature_f_is_correct_conversion(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_weather("Anywhere")
        expected_f = round(result["temperature_c"] * 9 / 5 + 32, 1)
        assert result["temperature_f"] == expected_f

    @pytest.mark.asyncio
    async def test_city_name_is_title_cased(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_weather("new york city")
        assert result["city"] == "New York City"

    @pytest.mark.asyncio
    async def test_mock_note_indicates_mock_data(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_weather("London")
        assert "MOCK DATA" in result.get("note", "")

    @pytest.mark.asyncio
    async def test_numeric_fields_are_numeric(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_weather("TestCity")
        assert isinstance(result["temperature_c"], (int, float))
        assert isinstance(result["temperature_f"], (int, float))
        assert isinstance(result["humidity_percent"], (int, float))

    @pytest.mark.asyncio
    async def test_humidity_in_reasonable_range(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_weather("Anywhere")
        assert 0 <= result["humidity_percent"] <= 100


class TestMockForecastData:
    """Mock forecast returns valid date-ordered entries."""

    @pytest.mark.asyncio
    async def test_forecast_has_city_and_forecast_list(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_forecast("Tokyo", days=3)
        assert "city" in result
        assert "forecast" in result

    @pytest.mark.asyncio
    async def test_forecast_city_is_title_cased(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_forecast("san francisco", days=2)
        assert result["city"] == "San Francisco"

    @pytest.mark.asyncio
    async def test_forecast_length_matches_requested_days(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        for days in (1, 3, 5):
            result = await tools_mod.get_forecast("London", days=days)
            assert len(result["forecast"]) == days

    @pytest.mark.asyncio
    async def test_forecast_capped_at_five_days(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_forecast("Berlin", days=10)
        assert len(result["forecast"]) <= 5

    @pytest.mark.asyncio
    async def test_forecast_dates_are_sequential(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_forecast("Paris", days=4)
        dates = [datetime.date.fromisoformat(d["date"]) for d in result["forecast"]]
        for i in range(1, len(dates)):
            assert dates[i] > dates[i - 1], "Forecast dates must be in ascending order"

    @pytest.mark.asyncio
    async def test_forecast_entries_have_all_required_fields(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_forecast("Rome", days=2)
        for entry in result["forecast"]:
            assert "date" in entry
            assert "high_c" in entry
            assert "low_c" in entry
            assert "conditions" in entry

    @pytest.mark.asyncio
    async def test_forecast_high_is_greater_or_equal_to_low(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "")
        result = await tools_mod.get_forecast("Madrid", days=3)
        for entry in result["forecast"]:
            assert entry["high_c"] >= entry["low_c"]


# ── OWM API error handling (with mocked httpx) ────────────────────────────────


class TestOWMApiErrorHandling:
    """get_weather handles HTTP errors and unexpected responses gracefully."""

    @pytest.mark.asyncio
    async def test_city_not_found_404_returns_error_dict(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "fake-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tools_mod.get_weather("NonexistentCity999")

        assert "error" in result
        assert "NonexistentCity999" in result["error"]

    @pytest.mark.asyncio
    async def test_successful_response_parsed_to_correct_fields(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "fake-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "Paris",
            "sys": {"country": "FR"},
            "main": {"temp": 15.0, "feels_like": 13.5, "humidity": 72},
            "wind": {"speed": 3.1},
            "weather": [{"main": "Clouds", "description": "overcast clouds"}],
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tools_mod.get_weather("Paris")

        assert result["city"] == "Paris"
        assert result["country"] == "FR"
        assert result["temperature_c"] == 15.0
        assert result["temperature_f"] == round(15.0 * 9 / 5 + 32, 1)
        assert result["conditions"] == "Clouds"
        assert result["humidity_percent"] == 72

    @pytest.mark.asyncio
    async def test_network_error_returns_error_dict(self, monkeypatch):
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "fake-key")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tools_mod.get_weather("London")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_malformed_api_response_returns_error_dict(self, monkeypatch):
        """A response missing expected keys should return an error dict, not raise."""
        import weather_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "OPENWEATHERMAP_API_KEY", "fake-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"unexpected": "structure"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tools_mod.get_weather("London")

        assert "error" in result
