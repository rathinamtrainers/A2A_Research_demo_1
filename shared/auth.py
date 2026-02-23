"""
Authentication utilities for the A2A Protocol Demo.

Provides helpers for every auth scheme demonstrated in the project:
- No auth (open)         → weather_agent (local dev)
- API Key header         → code_agent (X-API-Key)
- Bearer (JWT)           → research_agent (simulated OAuth)
- OAuth 2.0 (GCP SA)     → data_agent

These utilities are intentionally lightweight — this is a *demo*.
Production deployments should use a proper auth library.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from shared.config import settings

# ── API Key (code_agent) ──────────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(_api_key_header)) -> str:
    """
    FastAPI dependency that validates the ``X-API-Key`` header.

    Raises ``HTTP 403`` if the key is missing or invalid.

    Args:
        api_key: Value extracted from the ``X-API-Key`` request header.

    Returns:
        The validated API key string.

    Raises:
        HTTPException: 403 if key is absent or does not match.
    """
    # TODO: Replace with constant-time comparison / lookup in secret store
    if not api_key or api_key != settings.CODE_AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    return api_key


# ── Bearer JWT (research_agent) ───────────────────────────────────────────────

_http_bearer = HTTPBearer(auto_error=False)


def create_bearer_token(subject: str, ttl_seconds: int = 3600) -> str:
    """
    Create a minimal HMAC-signed Bearer token for demo purposes.

    This is NOT a production-quality JWT — it uses HMAC-SHA256 over a
    JSON payload without a proper library.  Replace with ``python-jose``
    or ``authlib`` for production.

    Args:
        subject: The token subject (e.g. ``"demo-client"``).
        ttl_seconds: Token lifetime in seconds.

    Returns:
        A ``"<header>.<payload>.<signature>"`` string.
    """
    # TODO: Replace with a proper JWT library in production
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    payload_data = {
        "sub": subject,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
    }
    payload = base64.urlsafe_b64encode(
        json.dumps(payload_data).encode()
    ).rstrip(b"=").decode()

    signing_input = f"{header}.{payload}"
    sig = hmac.new(
        settings.RESEARCH_AGENT_JWT_SECRET.encode(),
        signing_input.encode(),
        hashlib.sha256,
    ).digest()
    signature = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    return f"{signing_input}.{signature}"


def verify_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_http_bearer),
) -> dict:
    """
    FastAPI dependency that validates a Bearer token.

    Args:
        credentials: Extracted by ``HTTPBearer`` from the ``Authorization`` header.

    Returns:
        The decoded payload dict.

    Raises:
        HTTPException: 401 if token is missing, malformed, or expired.
    """
    # TODO: Replace with a proper JWT verification library
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
        )

    token = credentials.credentials
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token")

        # Verify signature
        signing_input = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(
            settings.RESEARCH_AGENT_JWT_SECRET.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        actual_sig = base64.urlsafe_b64decode(parts[2] + "==")
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid signature")

        # Decode payload
        payload = json.loads(
            base64.urlsafe_b64decode(parts[1] + "==").decode()
        )

        # Check expiry
        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expired")

        return payload

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Bearer token: {exc}",
        ) from exc


# ── Webhook HMAC verification ─────────────────────────────────────────────────

def verify_webhook_signature(request_body: bytes, signature_header: str) -> bool:
    """
    Verify an HMAC-SHA256 webhook delivery signature.

    The sender is expected to set ``X-Webhook-Signature: sha256=<hex>`` on
    every delivery.

    Args:
        request_body: Raw request body bytes.
        signature_header: Value of the ``X-Webhook-Signature`` header.

    Returns:
        ``True`` if the signature is valid, ``False`` otherwise.
    """
    # TODO: Implement in webhook_server/main.py
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.WEBHOOK_AUTH_TOKEN.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()
    actual = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, actual)
