"""
Weather tool functions for the Weather Agent.

These are plain Python functions registered as ADK function tools (F12).
ADK auto-generates JSON schemas from type annotations + docstrings.

Data source: OpenWeatherMap API (free tier).
Fallback: Returns deterministic mock data when no API key is configured.
"""

from __future__ import annotations

import datetime
from collections import defaultdict

import httpx

from shared.config import settings

_OWM_BASE = "https://api.openweathermap.org/data/2.5"


def get_weather(city: str) -> dict:
    """
    Return current weather conditions for a city.

    Calls the OpenWeatherMap ``/weather`` endpoint.  If no API key is
    configured (``OPENWEATHERMAP_API_KEY`` is empty), returns mock data
    so the demo works without a real API key.

    Args:
        city: City name, e.g. ``"London"`` or ``"New York"``.

    Returns:
        A dict with keys: ``city``, ``country``, ``temperature_c``,
        ``temperature_f``, ``feels_like_c``, ``humidity_percent``,
        ``wind_speed_ms``, ``conditions``, ``description``.
    """
    if not settings.OPENWEATHERMAP_API_KEY:
        # TODO: Remove mock data once real API key is configured
        return _mock_weather(city)

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{_OWM_BASE}/weather",
                params={
                    "q": city,
                    "appid": settings.OPENWEATHERMAP_API_KEY,
                    "units": "metric",
                },
            )
            if resp.status_code == 404:
                return {"error": f"City not found: {city}"}
            resp.raise_for_status()
            data = resp.json()

        temp_c = data["main"]["temp"]
        return {
            "city": data["name"],
            "country": data["sys"]["country"],
            "temperature_c": round(temp_c, 1),
            "temperature_f": round(temp_c * 9 / 5 + 32, 1),
            "feels_like_c": round(data["main"]["feels_like"], 1),
            "humidity_percent": data["main"]["humidity"],
            "wind_speed_ms": data["wind"]["speed"],
            "conditions": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
        }
    except httpx.HTTPError as exc:
        return {"error": f"Weather API request failed: {exc}"}
    except KeyError as exc:
        return {"error": f"Unexpected API response structure: {exc}"}


def get_forecast(city: str, days: int = 5) -> dict:
    """
    Return a multi-day weather forecast for a city.

    Calls the OpenWeatherMap ``/forecast`` endpoint (3-hour intervals,
    aggregated to daily highs/lows).  Falls back to mock data when no
    API key is set.

    Args:
        city: City name, e.g. ``"Tokyo"``.
        days: Number of forecast days (1–5, default 5).

    Returns:
        A dict with ``city`` and a ``forecast`` list, each entry having
        ``date``, ``high_c``, ``low_c``, ``conditions``.
    """
    if not settings.OPENWEATHERMAP_API_KEY:
        # TODO: Remove mock data once real API key is configured
        return _mock_forecast(city, days)

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{_OWM_BASE}/forecast",
                params={
                    "q": city,
                    "appid": settings.OPENWEATHERMAP_API_KEY,
                    "units": "metric",
                    "cnt": days * 8,  # 8 x 3h intervals per day
                },
            )
            if resp.status_code == 404:
                return {"error": f"City not found: {city}"}
            resp.raise_for_status()
            data = resp.json()

        return {
            "city": data["city"]["name"],
            "forecast": _aggregate_forecast(data["list"], days),
        }
    except httpx.HTTPError as exc:
        return {"error": f"Forecast API request failed: {exc}"}


# ── OWM response aggregation ──────────────────────────────────────────────────

def _aggregate_forecast(slots: list, days: int) -> list:
    """
    Aggregate 3-hour OWM forecast slots into daily high/low summaries.

    The OWM ``/forecast`` endpoint returns data in 3-hour intervals.
    This function groups slots by calendar date and computes the daily
    high temperature, low temperature, and dominant weather condition.

    Args:
        slots: List of 3-hour forecast dicts from the OWM ``list`` field.
        days: Maximum number of days to return.

    Returns:
        A list of dicts with ``date``, ``high_c``, ``low_c``, ``conditions``.
    """
    # Group slots by date (YYYY-MM-DD)
    by_date: dict[str, list] = defaultdict(list)
    for slot in slots:
        dt_txt = slot.get("dt_txt", "")
        date_str = dt_txt.split(" ")[0] if " " in dt_txt else str(slot.get("dt", ""))[:10]
        if date_str:
            by_date[date_str].append(slot)

    result = []
    for date_str in sorted(by_date.keys())[:days]:
        day_slots = by_date[date_str]
        temps = [s["main"]["temp"] for s in day_slots if "main" in s]
        conditions_counts: dict[str, int] = defaultdict(int)
        for s in day_slots:
            if "weather" in s and s["weather"]:
                conditions_counts[s["weather"][0]["main"]] += 1

        dominant_condition = max(conditions_counts, key=conditions_counts.get) if conditions_counts else "Unknown"

        if temps:
            result.append({
                "date": date_str,
                "high_c": round(max(temps), 1),
                "low_c": round(min(temps), 1),
                "conditions": dominant_condition,
            })

    return result


# ── Mock data helpers ─────────────────────────────────────────────────────────

def _mock_weather(city: str) -> dict:
    """Return deterministic mock weather for any city (no API key needed)."""
    return {
        "city": city.title(),
        "country": "XX",
        "temperature_c": 18.5,
        "temperature_f": 65.3,
        "feels_like_c": 17.0,
        "humidity_percent": 62,
        "wind_speed_ms": 3.2,
        "conditions": "Clouds",
        "description": "scattered clouds",
        "note": "MOCK DATA — set OPENWEATHERMAP_API_KEY for real data",
    }


def _mock_forecast(city: str, days: int) -> dict:
    """Return deterministic mock forecast for any city."""
    import datetime

    today = datetime.date.today()
    forecast = []
    for i in range(min(days, 5)):
        date = today + datetime.timedelta(days=i)
        forecast.append({
            "date": str(date),
            "high_c": 20 + i,
            "low_c": 12 + i,
            "conditions": "Partly Cloudy",
        })
    return {
        "city": city.title(),
        "forecast": forecast,
        "note": "MOCK DATA — set OPENWEATHERMAP_API_KEY for real data",
    }
