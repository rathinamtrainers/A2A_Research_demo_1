"""
Tests for shared/config.py — Settings dataclass loading and validation.

Reference: F0.1 — Environment & Configuration.
"""

from __future__ import annotations

import pytest

from shared.config import Settings


class TestSettingsDefaults:
    """Settings fields have correct defaults when env vars are absent."""

    def test_default_gemini_model(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        s = Settings()
        assert s.GEMINI_MODEL == "gemini-2.0-flash"

    def test_default_cloud_location(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        s = Settings()
        assert s.GOOGLE_CLOUD_LOCATION == "us-central1"

    def test_default_weather_agent_url(self, monkeypatch):
        monkeypatch.delenv("WEATHER_AGENT_URL", raising=False)
        s = Settings()
        assert s.WEATHER_AGENT_URL == "http://localhost:8001"

    def test_default_research_agent_url(self, monkeypatch):
        monkeypatch.delenv("RESEARCH_AGENT_URL", raising=False)
        s = Settings()
        assert s.RESEARCH_AGENT_URL == "http://localhost:8002"

    def test_default_code_agent_url(self, monkeypatch):
        monkeypatch.delenv("CODE_AGENT_URL", raising=False)
        s = Settings()
        assert s.CODE_AGENT_URL == "http://localhost:8003"

    def test_default_async_agent_url(self, monkeypatch):
        monkeypatch.delenv("ASYNC_AGENT_URL", raising=False)
        s = Settings()
        assert s.ASYNC_AGENT_URL == "http://localhost:8005"

    def test_default_webhook_server_url(self, monkeypatch):
        monkeypatch.delenv("WEBHOOK_SERVER_URL", raising=False)
        s = Settings()
        assert s.WEBHOOK_SERVER_URL == "http://localhost:9000"

    def test_default_code_agent_api_key(self, monkeypatch):
        monkeypatch.delenv("CODE_AGENT_API_KEY", raising=False)
        s = Settings()
        assert s.CODE_AGENT_API_KEY == "demo-code-agent-key-12345"

    def test_default_openweathermap_key_is_empty(self, monkeypatch):
        monkeypatch.delenv("OPENWEATHERMAP_API_KEY", raising=False)
        s = Settings()
        assert s.OPENWEATHERMAP_API_KEY == ""

    def test_env_var_overrides_default_url(self, monkeypatch):
        monkeypatch.setenv("WEATHER_AGENT_URL", "https://weather.example.com")
        s = Settings()
        assert s.WEATHER_AGENT_URL == "https://weather.example.com"

    def test_env_var_overrides_default_api_key(self, monkeypatch):
        monkeypatch.setenv("CODE_AGENT_API_KEY", "custom-key-xyz")
        s = Settings()
        assert s.CODE_AGENT_API_KEY == "custom-key-xyz"


class TestSettingsValidateSuccess:
    """Settings.validate() passes with valid configurations."""

    def test_validate_passes_with_all_fields_set_vertexai_disabled(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = "some-token"
        s.CODE_AGENT_API_KEY = "some-key"
        s.RESEARCH_AGENT_JWT_SECRET = "some-secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = "0"
        # Should not raise
        s.validate()

    def test_validate_passes_when_vertexai_disabled_without_project(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = "token"
        s.CODE_AGENT_API_KEY = "key"
        s.RESEARCH_AGENT_JWT_SECRET = "secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = "0"
        s.GOOGLE_CLOUD_PROJECT = ""
        # Should not raise — project not required when VertexAI is disabled
        s.validate()

    def test_validate_passes_with_vertexai_false_string(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = "token"
        s.CODE_AGENT_API_KEY = "key"
        s.RESEARCH_AGENT_JWT_SECRET = "secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = "false"
        s.GOOGLE_CLOUD_PROJECT = ""
        s.validate()

    def test_validate_passes_with_vertexai_false_capital(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = "token"
        s.CODE_AGENT_API_KEY = "key"
        s.RESEARCH_AGENT_JWT_SECRET = "secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = "False"
        s.GOOGLE_CLOUD_PROJECT = ""
        s.validate()

    def test_validate_passes_with_vertexai_enabled_and_project_set(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = "token"
        s.CODE_AGENT_API_KEY = "key"
        s.RESEARCH_AGENT_JWT_SECRET = "secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = "1"
        s.GOOGLE_CLOUD_PROJECT = "my-project-id"
        s.validate()


class TestSettingsValidateFailures:
    """Settings.validate() raises ValueError for missing required vars."""

    def test_raises_on_empty_webhook_auth_token(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = ""
        s.CODE_AGENT_API_KEY = "key"
        s.RESEARCH_AGENT_JWT_SECRET = "secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = "0"
        with pytest.raises(ValueError, match="WEBHOOK_AUTH_TOKEN"):
            s.validate()

    def test_raises_on_empty_code_agent_api_key(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = "token"
        s.CODE_AGENT_API_KEY = ""
        s.RESEARCH_AGENT_JWT_SECRET = "secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = "0"
        with pytest.raises(ValueError, match="CODE_AGENT_API_KEY"):
            s.validate()

    def test_raises_on_empty_jwt_secret(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = "token"
        s.CODE_AGENT_API_KEY = "key"
        s.RESEARCH_AGENT_JWT_SECRET = ""
        s.GOOGLE_GENAI_USE_VERTEXAI = "0"
        with pytest.raises(ValueError, match="RESEARCH_AGENT_JWT_SECRET"):
            s.validate()

    def test_raises_when_vertexai_enabled_without_project(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = "token"
        s.CODE_AGENT_API_KEY = "key"
        s.RESEARCH_AGENT_JWT_SECRET = "secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = "1"
        s.GOOGLE_CLOUD_PROJECT = ""
        with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
            s.validate()

    def test_error_message_contains_env_setup_instructions(self):
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = ""
        s.CODE_AGENT_API_KEY = "key"
        s.RESEARCH_AGENT_JWT_SECRET = "secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = "0"
        with pytest.raises(ValueError, match="ENV_SETUP.md"):
            s.validate()

    def test_raises_and_reports_all_missing_vars_at_once(self):
        """validate() should aggregate all missing vars and report them together."""
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = ""
        s.CODE_AGENT_API_KEY = ""
        s.RESEARCH_AGENT_JWT_SECRET = ""
        s.GOOGLE_GENAI_USE_VERTEXAI = "0"
        with pytest.raises(ValueError) as exc_info:
            s.validate()
        error_msg = str(exc_info.value)
        assert "WEBHOOK_AUTH_TOKEN" in error_msg
        assert "CODE_AGENT_API_KEY" in error_msg
        assert "RESEARCH_AGENT_JWT_SECRET" in error_msg

    def test_vertexai_enabled_with_empty_string_value_requires_project(self):
        """GOOGLE_GENAI_USE_VERTEXAI='' is treated as disabled, so no project needed."""
        s = Settings()
        s.WEBHOOK_AUTH_TOKEN = "token"
        s.CODE_AGENT_API_KEY = "key"
        s.RESEARCH_AGENT_JWT_SECRET = "secret"
        s.GOOGLE_GENAI_USE_VERTEXAI = ""
        s.GOOGLE_CLOUD_PROJECT = ""
        # Empty string means disabled — should not raise for project
        s.validate()


class TestSettingsDataclassStructure:
    """Settings is a proper dataclass with expected fields."""

    def test_settings_has_all_expected_attributes(self):
        s = Settings()
        required_attrs = [
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_LOCATION",
            "GOOGLE_GENAI_USE_VERTEXAI",
            "GEMINI_MODEL",
            "WEATHER_AGENT_URL",
            "RESEARCH_AGENT_URL",
            "CODE_AGENT_URL",
            "DATA_AGENT_URL",
            "ASYNC_AGENT_URL",
            "WEBHOOK_SERVER_URL",
            "WEBHOOK_AUTH_TOKEN",
            "CODE_AGENT_API_KEY",
            "RESEARCH_AGENT_JWT_SECRET",
            "OPENWEATHERMAP_API_KEY",
        ]
        for attr in required_attrs:
            assert hasattr(s, attr), f"Settings missing expected attribute: {attr}"

    def test_all_url_fields_are_strings(self):
        s = Settings()
        url_fields = [
            s.WEATHER_AGENT_URL,
            s.RESEARCH_AGENT_URL,
            s.CODE_AGENT_URL,
            s.DATA_AGENT_URL,
            s.ASYNC_AGENT_URL,
            s.WEBHOOK_SERVER_URL,
        ]
        for url in url_fields:
            assert isinstance(url, str)

    def test_settings_can_be_mutated_for_testing(self):
        """Settings fields can be overridden in tests via direct assignment."""
        s = Settings()
        s.CODE_AGENT_API_KEY = "override-value"
        assert s.CODE_AGENT_API_KEY == "override-value"
