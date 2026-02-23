"""
Tests for shared authentication utilities.

Reference: F8 — Authentication Schemes.

Note on settings singleton: `shared.config.settings` is initialized once at
import time from environment variables. Tests that need specific settings values
must use ``monkeypatch.setattr`` to patch the singleton object directly, not
``monkeypatch.setenv`` (which only affects os.environ after import).
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import shared.auth as auth_module


class TestApiKeyVerification:
    """Tests for verify_api_key."""

    def test_valid_api_key_passes(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "CODE_AGENT_API_KEY", "my-test-key")
        result = auth_module.verify_api_key(api_key="my-test-key")
        assert result == "my-test-key"

    def test_missing_api_key_raises_403(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "CODE_AGENT_API_KEY", "expected-key")
        with pytest.raises(HTTPException) as exc_info:
            auth_module.verify_api_key(api_key=None)
        assert exc_info.value.status_code == 403

    def test_wrong_api_key_raises_403(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "CODE_AGENT_API_KEY", "correct-key")
        with pytest.raises(HTTPException) as exc_info:
            auth_module.verify_api_key(api_key="wrong-key")
        assert exc_info.value.status_code == 403

    def test_empty_string_api_key_raises_403(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "CODE_AGENT_API_KEY", "expected-key")
        with pytest.raises(HTTPException) as exc_info:
            auth_module.verify_api_key(api_key="")
        assert exc_info.value.status_code == 403


class TestBearerTokens:
    """Tests for Bearer token creation and verification."""

    def test_create_and_verify_token(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "RESEARCH_AGENT_JWT_SECRET", "test-secret")
        token = auth_module.create_bearer_token("test-subject", ttl_seconds=300)
        assert token.count(".") == 2  # header.payload.signature

        creds = HTTPAuthorizationCredentials(scheme="bearer", credentials=token)
        payload = auth_module.verify_bearer_token(credentials=creds)
        assert payload["sub"] == "test-subject"

    def test_expired_token_raises_401(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "RESEARCH_AGENT_JWT_SECRET", "test-secret")
        token = auth_module.create_bearer_token("test-subject", ttl_seconds=-1)
        creds = HTTPAuthorizationCredentials(scheme="bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            auth_module.verify_bearer_token(credentials=creds)
        assert exc_info.value.status_code == 401

    def test_tampered_token_raises_401(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "RESEARCH_AGENT_JWT_SECRET", "test-secret")
        token = auth_module.create_bearer_token("test-subject", ttl_seconds=300)
        tampered = token[:-5] + "xxxxx"
        creds = HTTPAuthorizationCredentials(scheme="bearer", credentials=tampered)
        with pytest.raises(HTTPException) as exc_info:
            auth_module.verify_bearer_token(credentials=creds)
        assert exc_info.value.status_code == 401

    def test_missing_bearer_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            auth_module.verify_bearer_token(credentials=None)
        assert exc_info.value.status_code == 401

    def test_wrong_scheme_raises_401(self):
        creds = HTTPAuthorizationCredentials(scheme="Basic", credentials="dXNlcjpwYXNz")
        with pytest.raises(HTTPException) as exc_info:
            auth_module.verify_bearer_token(credentials=creds)
        assert exc_info.value.status_code == 401


class TestWebhookSignatureVerification:
    """Tests for verify_webhook_signature."""

    def test_valid_signature_returns_true(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "WEBHOOK_AUTH_TOKEN", "test-secret")
        body = b'{"event":"test"}'
        sig = hmac_mod.new(b"test-secret", body, hashlib.sha256).hexdigest()
        assert auth_module.verify_webhook_signature(body, f"sha256={sig}") is True

    def test_invalid_signature_returns_false(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "WEBHOOK_AUTH_TOKEN", "test-secret")
        assert auth_module.verify_webhook_signature(b"body", "sha256=invalidsig") is False

    def test_missing_prefix_returns_false(self):
        assert auth_module.verify_webhook_signature(b"body", "invalidsig") is False

    def test_empty_body_valid_sig(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "WEBHOOK_AUTH_TOKEN", "test-secret")
        body = b""
        sig = hmac_mod.new(b"test-secret", body, hashlib.sha256).hexdigest()
        assert auth_module.verify_webhook_signature(body, f"sha256={sig}") is True
