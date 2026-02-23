"""
Centralised configuration loader for the A2A Protocol Demo.

Loads values from the .env file (or environment) and exposes them as a
typed ``Settings`` dataclass.  All agent modules import from here so that
environment variables are only resolved in one place.

Usage::

    from shared.config import settings
    print(settings.GOOGLE_CLOUD_PROJECT)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)


@dataclass
class Settings:
    """All environment-driven configuration for the demo."""

    # ── GCP / Vertex AI ──────────────────────────────────────────────────
    GOOGLE_CLOUD_PROJECT: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    )
    GOOGLE_CLOUD_LOCATION: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    )
    GOOGLE_GENAI_USE_VERTEXAI: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "1")
    )
    VERTEXAI_STAGING_BUCKET: str = field(
        default_factory=lambda: os.environ.get("VERTEXAI_STAGING_BUCKET", "")
    )

    # ── Gemini model ──────────────────────────────────────────────────────
    GEMINI_MODEL: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    )

    # ── A2A Agent URLs (local dev defaults) ──────────────────────────────
    WEATHER_AGENT_URL: str = field(
        default_factory=lambda: os.environ.get("WEATHER_AGENT_URL", "http://localhost:8001")
    )
    RESEARCH_AGENT_URL: str = field(
        default_factory=lambda: os.environ.get("RESEARCH_AGENT_URL", "http://localhost:8002")
    )
    CODE_AGENT_URL: str = field(
        default_factory=lambda: os.environ.get("CODE_AGENT_URL", "http://localhost:8003")
    )
    DATA_AGENT_URL: str = field(
        default_factory=lambda: os.environ.get("DATA_AGENT_URL", "http://localhost:8004")
    )
    ASYNC_AGENT_URL: str = field(
        default_factory=lambda: os.environ.get("ASYNC_AGENT_URL", "http://localhost:8005")
    )

    # ── Webhook server ────────────────────────────────────────────────────
    WEBHOOK_SERVER_URL: str = field(
        default_factory=lambda: os.environ.get("WEBHOOK_SERVER_URL", "http://localhost:9000")
    )
    WEBHOOK_AUTH_TOKEN: str = field(
        default_factory=lambda: os.environ.get("WEBHOOK_AUTH_TOKEN", "demo-webhook-secret-token")
    )

    # ── API Keys for demo auth schemes ────────────────────────────────────
    CODE_AGENT_API_KEY: str = field(
        default_factory=lambda: os.environ.get("CODE_AGENT_API_KEY", "demo-code-agent-key-12345")
    )
    RESEARCH_AGENT_JWT_SECRET: str = field(
        default_factory=lambda: os.environ.get("RESEARCH_AGENT_JWT_SECRET", "demo-jwt-secret")
    )

    # ── OpenWeatherMap ────────────────────────────────────────────────────
    OPENWEATHERMAP_API_KEY: str = field(
        default_factory=lambda: os.environ.get("OPENWEATHERMAP_API_KEY", "")
    )

    # ── Observability ─────────────────────────────────────────────────────
    OTEL_EXPORTER_OTLP_ENDPOINT: str = field(
        default_factory=lambda: os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "https://telemetry.googleapis.com"
        )
    )

    def validate(self) -> None:
        """
        Validate that all required environment variables are present.

        Raises ``ValueError`` listing every missing variable if any are absent.
        Required variables are those whose absence would cause runtime failures
        in a production deployment (GCP credentials and security secrets).

        In local development with ``GOOGLE_GENAI_USE_VERTEXAI=0`` (AI Studio),
        ``GOOGLE_CLOUD_PROJECT`` is not required.
        """
        missing: list[str] = []

        # Auth secrets must always be set to non-default values in production.
        # We check they are non-empty (defaults are acceptable in dev/test).
        if not self.WEBHOOK_AUTH_TOKEN:
            missing.append("WEBHOOK_AUTH_TOKEN")
        if not self.CODE_AGENT_API_KEY:
            missing.append("CODE_AGENT_API_KEY")
        if not self.RESEARCH_AGENT_JWT_SECRET:
            missing.append("RESEARCH_AGENT_JWT_SECRET")

        # GCP project required when Vertex AI is enabled
        use_vertexai = self.GOOGLE_GENAI_USE_VERTEXAI not in ("0", "false", "False", "")
        if use_vertexai and not self.GOOGLE_CLOUD_PROJECT:
            missing.append(
                "GOOGLE_CLOUD_PROJECT (required when GOOGLE_GENAI_USE_VERTEXAI=1)"
            )

        if missing:
            raise ValueError(
                "Missing required environment variables:\n  - "
                + "\n  - ".join(missing)
                + "\nSee ENV_SETUP.md for configuration instructions."
            )


# Singleton instance used across the project
settings = Settings()
