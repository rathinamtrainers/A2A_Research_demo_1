# Speaker Notes — `weather_agent/tools.py`

> **File**: `weather_agent/tools.py` (204 lines)
> **Purpose**: Weather tool functions (current conditions + forecast) with OpenWeatherMap API integration and mock fallback.
> **Estimated teaching time**: 15–20 minutes
> **A2A Features covered**: F12 (Custom Function Tools)

---

## Why This File Matters

This file is the **concrete implementation** behind the weather agent's
capabilities. While `agent.py` defines *what* the agent is and *how* it is
exposed, this file defines *what the agent can actually do*.

It is also the best file in the project for teaching three critical
production patterns:

1. **Graceful degradation** — Falls back to mock data when no API key is set.
2. **Async HTTP with proper timeouts** — Uses `httpx.AsyncClient` instead of blocking `requests`.
3. **ADK function tool conventions** — Type annotations and docstrings that ADK auto-converts to JSON schemas for Gemini function calling.

---

## Section-by-Section Walkthrough

### 1. Module Docstring and Imports (lines 1–18)

```python
import datetime
from collections import defaultdict

import httpx

from shared.config import settings

_OWM_BASE = "https://api.openweathermap.org/data/2.5"
```

**Explain to students:**

- **`httpx`** is used instead of `requests` because these are `async def` functions. `httpx.AsyncClient` supports `await` natively. Using `requests` (which is synchronous) inside an `async def` would block the event loop and destroy concurrency.
- **`defaultdict`** from `collections` is used in `_aggregate_forecast` to group forecast slots by date. This is a Pythonic way to avoid `if key not in dict` checks.
- **`_OWM_BASE`** — The OpenWeatherMap API base URL is a module-level constant. The underscore prefix signals it is private to this module.
- **`settings`** — The only configuration this file needs is `settings.OPENWEATHERMAP_API_KEY`. It does not import agent URLs or model names because tools do not need to know about the agent infrastructure.

**Teaching moment**: Notice how thin the imports are. This file has no dependency on `google.adk`, no dependency on `a2a.types`, no dependency on FastAPI. It is a pure Python module that happens to be used as an ADK tool. This is intentional — tools should be testable in isolation, without starting an agent or a server.

---

### 2. `get_weather()` — Current Conditions (lines 23–73)

```python
async def get_weather(city: str) -> dict:
    """
    Return current weather conditions for a city.

    Args:
        city: City name, e.g. ``"London"`` or ``"New York"``.

    Returns:
        A dict with keys: ``city``, ``country``, ``temperature_c``,
        ``temperature_f``, ``feels_like_c``, ``humidity_percent``,
        ``wind_speed_ms``, ``conditions``, ``description``.
    """
```

**Explain to students:**

- **This is how ADK function tools work (F12).** You write a plain Python function with type annotations and a docstring. ADK inspects these at agent construction time to generate a JSON schema that Gemini uses for function calling. No decorators, no schema files, no registration code.
- **The type annotations matter**: `city: str` tells Gemini this parameter is a string. `-> dict` tells ADK the return type. If you omit these, Gemini will not know how to call the function.
- **The docstring matters**: ADK extracts the function description and parameter descriptions from the docstring. Gemini sees this as part of the function-calling schema. A vague docstring leads to vague tool usage.

#### 2a. Mock Data Fallback (lines 39–41)

```python
if not settings.OPENWEATHERMAP_API_KEY:
    return _mock_weather(city)
```

**Explain to students:**

- **Graceful degradation**: If no API key is configured, the function returns deterministic mock data instead of failing. This means the demo works out of the box, without requiring students to sign up for an OpenWeatherMap account.
- **The check is simple**: empty string is falsy in Python. The `OPENWEATHERMAP_API_KEY` defaults to `""` in `shared/config.py`.
- **The `TODO` comment** acknowledges this is a development convenience, not a production pattern. In production, you would either require the API key or have a more sophisticated fallback (e.g., a cache of recent data).

#### 2b. API Call with httpx (lines 43–56)

```python
async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.get(
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
```

**Explain to students:**

- **`async with httpx.AsyncClient(timeout=10.0)`** — Creates a new HTTP client for each call with a 10-second timeout. The `async with` ensures the client is properly closed after use (connection cleanup). The timeout prevents the agent from hanging indefinitely if OpenWeatherMap is slow or down.
- **`params` dict** — `httpx` URL-encodes these automatically. `"units": "metric"` means temperatures come back in Celsius.
- **404 handling** — A 404 from OpenWeatherMap means the city was not found. Instead of raising an exception, the function returns a structured error dict. The LLM sees this and can tell the user "I couldn't find that city."
- **`raise_for_status()`** — For non-404 errors (500, 429 rate limit, etc.), this raises an `httpx.HTTPStatusError`, which is caught by the outer `except`.

**Teaching moment**: The pattern of checking specific status codes before calling `raise_for_status()` is important. You want to handle **expected** errors (city not found) gracefully and let **unexpected** errors (server down) propagate to the exception handler.

#### 2c. Response Transformation (lines 58–69)

```python
temp_c = data["main"]["temp"]
return {
    "city": data["name"],
    "country": data["sys"]["country"],
    "temperature_c": round(temp_c, 1),
    "temperature_f": round(temp_c * 9 / 5 + 32, 1),
    "temperature_f": round(temp_c * 9 / 5 + 32, 1),
    "feels_like_c": round(data["main"]["feels_like"], 1),
    "humidity_percent": data["main"]["humidity"],
    "wind_speed_ms": data["wind"]["speed"],
    "conditions": data["weather"][0]["main"],
    "description": data["weather"][0]["description"],
}
```

**Explain to students:**

- **The function does not return the raw API response.** It transforms it into a clean, flat dict with consistent keys. This is important because:
  - The LLM sees this dict as the tool's output. Clean keys make the LLM's response better.
  - The response structure matches what the system instruction asks for (temperature in C and F, conditions, humidity, wind speed).
- **Temperature conversion**: The API returns Celsius (due to `"units": "metric"`), and the function also computes Fahrenheit. This saves the LLM from doing arithmetic.
- **`round(..., 1)`** — Avoids floating-point noise like `18.500000000000004`.

#### 2d. Error Handling (lines 70–73)

```python
except httpx.HTTPError as exc:
    return {"error": f"Weather API request failed: {exc}"}
except KeyError as exc:
    return {"error": f"Unexpected API response structure: {exc}"}
```

**Explain to students:**

- **Two exception types, two failure modes:**
  - `httpx.HTTPError` — Network failures, timeouts, non-2xx status codes. The API is unreachable or unhappy.
  - `KeyError` — The API returned 200 OK but the JSON structure was not what we expected. This happens when APIs change their response format.
- **Both return error dicts** rather than raising exceptions. This is a critical ADK convention: tool functions should return error information in a dict so the LLM can reason about the failure and communicate it to the user. If the function raised an exception, ADK would catch it, but the LLM would see a generic error instead of a specific one.

**Teaching moment**: This is the "errors as values" pattern (common in Go, Rust, and functional programming). In agent systems, it is especially important because the LLM needs to understand *why* something failed to give a helpful response.

---

### 3. `get_forecast()` — Multi-Day Forecast (lines 76–117)

```python
async def get_forecast(city: str, days: int = 5) -> dict:
    """
    Return a multi-day weather forecast for a city.

    Args:
        city: City name, e.g. ``"Tokyo"``.
        days: Number of forecast days (1-5, default 5).
    """
```

**Explain to students:**

- **Second parameter with a default**: `days: int = 5`. ADK translates this into a JSON schema where `days` is an optional integer parameter with a default of 5. Gemini can omit it if the user just says "forecast for Tokyo" or provide it if the user says "3-day forecast for Tokyo."
- **`cnt=days * 8`** — The OpenWeatherMap free tier returns 3-hour intervals. To get N days, you need N * 8 slots (24 hours / 3 hours = 8 slots per day).

The structure mirrors `get_weather()`: check for API key, make the request, handle 404, transform the response, catch exceptions. Point out the consistency to students.

#### 3a. The Delegation to `_aggregate_forecast()` (line 114)

```python
return {
    "city": data["city"]["name"],
    "forecast": _aggregate_forecast(data["list"], days),
}
```

The raw API response contains 3-hour slots. The `_aggregate_forecast` helper transforms these into daily summaries. This keeps `get_forecast` focused on the API call and error handling.

---

### 4. `_aggregate_forecast()` — Data Aggregation (lines 120–164)

```python
def _aggregate_forecast(slots: list, days: int) -> list:
    # Group slots by date (YYYY-MM-DD)
    by_date: dict[str, list] = defaultdict(list)
    for slot in slots:
        dt_txt = slot.get("dt_txt", "")
        date_str = dt_txt.split(" ")[0] if " " in dt_txt else str(slot.get("dt", ""))[:10]
        if date_str:
            by_date[date_str].append(slot)
```

**Explain to students:**

- **This is a pure data transformation function.** It is not async, not a tool, and has no external dependencies. It takes raw API data and produces a clean summary.
- **Grouping by date**: The OWM `dt_txt` field is like `"2025-01-15 12:00:00"`. Splitting on space and taking the first part gives the date. The fallback `str(slot.get("dt", ""))[:10]` handles edge cases where `dt_txt` might be missing.
- **`defaultdict(list)`**: Each date key auto-initializes to an empty list. This avoids `if date_str not in by_date: by_date[date_str] = []`.

#### 4a. Computing Daily Summaries (lines 146–164)

```python
for date_str in sorted(by_date.keys())[:days]:
    day_slots = by_date[date_str]
    temps = [s["main"]["temp"] for s in day_slots if "main" in s]
    conditions_counts: dict[str, int] = defaultdict(int)
    for s in day_slots:
        if "weather" in s and s["weather"]:
            conditions_counts[s["weather"][0]["main"]] += 1

    dominant_condition = max(conditions_counts, key=conditions_counts.get) if conditions_counts else "Unknown"
```

**Explain to students:**

- **Daily high/low**: Extract all temperatures for the day, take `max()` and `min()`.
- **Dominant condition**: Count how often each condition appears across the day's slots, then take the most frequent one. If a day has 5 "Clouds" slots and 3 "Rain" slots, the dominant condition is "Clouds."
- **Defensive access**: `if "main" in s` and `if "weather" in s and s["weather"]` guard against malformed slots. API responses are not always perfectly structured.
- **`sorted(by_date.keys())[:days]`** — Sorts dates chronologically and takes only the requested number of days. The API might return data for more days than requested.

**Teaching moment**: This function demonstrates a common real-world pattern: bridging the gap between an external API's raw response format and the clean structure your application needs. APIs rarely return data in exactly the format you want.

---

### 5. Mock Data Helpers (lines 167–203)

```python
def _mock_weather(city: str) -> dict:
    return {
        "city": city.title(),
        "country": "XX",
        "temperature_c": 18.5,
        "temperature_f": 65.3,
        ...
        "note": "MOCK DATA -- set OPENWEATHERMAP_API_KEY for real data",
    }

def _mock_forecast(city: str, days: int) -> dict:
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
    return { "city": city.title(), "forecast": forecast, "note": "MOCK DATA ..." }
```

**Explain to students:**

- **Deterministic mock data**: Every call to `_mock_weather("London")` returns the exact same values. This makes tests predictable and demos reproducible.
- **`city.title()`** — Normalizes "london" to "London", matching what the real API would return.
- **The `"note"` field**: A visible signal that mock data is being returned. The LLM will include this in its response, so the user knows they are not seeing real weather data. This is important for demo honesty.
- **`_mock_forecast` uses relative dates**: `datetime.date.today() + timedelta(days=i)` generates dates starting from today. This means mock forecast output always looks current, not stale.
- **`min(days, 5)`** — Caps at 5 days, matching the real API's free-tier limit.
- **Both mocks match the real return schema exactly**: Same keys, same types, same structure. The only addition is the `"note"` key. This means the LLM and tests work identically with mock and real data.

**Teaching moment**: Mock data functions are often an afterthought, but well-designed mocks are essential for:
- Zero-config demos (students can run the project immediately)
- Reliable CI/CD (tests pass without external API keys)
- Offline development (planes, trains, coffee shops)
- Rate limit avoidance during development

---

## Design Patterns to Highlight

1. **Graceful Degradation**: The API key check at the top of each function is a feature flag that switches between real and mock implementations. The caller (the LLM agent) does not know or care which path is taken.

2. **Errors as Values**: Both `get_weather` and `get_forecast` return `{"error": "..."}` dicts instead of raising exceptions. This lets the LLM reason about failures and communicate them naturally to the user.

3. **Async I/O with Timeouts**: `httpx.AsyncClient(timeout=10.0)` ensures the agent never blocks indefinitely. In a concurrent system where multiple agents run in the same event loop, a blocking HTTP call in one tool would freeze all agents.

4. **Response Normalization**: Raw API responses are transformed into clean, flat dicts with consistent naming. The LLM works with `temperature_c`, not `data["main"]["temp"]`. This is the anti-corruption layer pattern from domain-driven design.

5. **Private Helpers**: Functions prefixed with `_` (`_aggregate_forecast`, `_mock_weather`, `_mock_forecast`) are implementation details. Only `get_weather` and `get_forecast` are part of the public API — the only two functions imported by `agent.py`.

6. **Schema-from-Code**: ADK generates JSON schemas from type annotations (`city: str`, `days: int = 5`) and docstrings. This is a form of documentation-driven development: the docstring is not just for humans, it is consumed by the framework.

---

## Common Student Questions

1. **"Why `httpx` instead of `aiohttp`?"** Both work. `httpx` was chosen because its API mirrors `requests` (familiar to most Python developers) and it supports both sync and async usage. `aiohttp` is equally valid but has a less familiar API.

2. **"Why create a new `AsyncClient` per call instead of reusing one?"** For simplicity in a demo. In production, you would create a long-lived client (perhaps at module level or in a dependency injection container) to benefit from connection pooling. The `async with` pattern here ensures the client is always cleaned up, even if an exception occurs.

3. **"What if the user asks for weather in a city that does not exist?"** The function returns `{"error": "City not found: xyz"}`. The LLM sees this error dict and responds naturally, e.g., "I couldn't find weather data for that city. Could you check the spelling?"

4. **"Why not use Pydantic models for the return type?"** Returning plain dicts keeps the tools dependency-free and easy to serialize. ADK expects tool functions to return dicts (or strings). Pydantic models could be used internally and converted with `.model_dump()`, but for a demo, plain dicts are simpler.

5. **"Is the mock data realistic enough for testing?"** The mock data has the same structure and reasonable values. For unit tests, this is sufficient. For integration tests that verify LLM response quality, you might want more varied mock data (e.g., different temperatures for different cities).

6. **"What happens if OpenWeatherMap rate-limits us?"** The API returns HTTP 429, which triggers `resp.raise_for_status()`, caught by `except httpx.HTTPError`. The function returns an error dict. For production, you would add retry logic with exponential backoff, or use the cache callback from `shared/callbacks.py`.

---

## Related Files

- `weather_agent/agent.py` — Imports `get_weather` and `get_forecast` and registers them as LlmAgent tools
- `shared/config.py` — Provides `settings.OPENWEATHERMAP_API_KEY` that controls real vs. mock behavior
- `shared/callbacks.py` — The `cache_callback_before_tool` / `cache_callback_after_tool` pair could be wired into the weather agent to cache API responses
- `tests/test_weather_tools.py` — Unit tests for both tool functions
- `.env.example` — Shows where to configure `OPENWEATHERMAP_API_KEY`
