# Speaker Notes — `shared/auth.py`

> **File**: `shared/auth.py` (185 lines)
> **Purpose**: Authentication utilities implementing every auth scheme in the A2A demo.
> **Estimated teaching time**: 15–20 minutes

---

## Why This File Matters

The A2A Protocol spec defines how agents advertise their authentication
requirements in the Agent Card (`securitySchemes`). This file provides the
**server-side verification** for three of those schemes. Every agent picks the
auth level appropriate to its sensitivity:

| Agent | Auth Scheme | Why |
|-------|-------------|-----|
| weather_agent | None (open) | Public data, no risk |
| code_agent | API Key (`X-API-Key`) | Executes code — must gate access |
| research_agent | Bearer JWT | Demonstrates token-based auth |
| data_agent | OAuth 2.0 (GCP SA) | Enterprise-grade, handled by GCP |

---

## Section-by-Section Walkthrough

### 1. Imports (lines 14–26)

```python
from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer
from shared.config import settings
```

**Explain to students:**

- FastAPI provides built-in security primitives: `APIKeyHeader` and `HTTPBearer`
  are **dependency injection** helpers. They automatically extract the relevant
  header from incoming requests and pass the value into your function.
- `Security(...)` is FastAPI's way of saying "this parameter comes from a
  security scheme, not from the request body or query string."
- All secrets come from `settings` — the single source of truth from `config.py`.

---

### 2. API Key Authentication (lines 28–54)

```python
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: Optional[str] = Security(_api_key_header)) -> str:
    if not api_key or api_key != settings.CODE_AGENT_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, ...)
    return api_key
```

**Explain to students:**

- `APIKeyHeader(name="X-API-Key", auto_error=False)` tells FastAPI: "look for
  a header called `X-API-Key`, but don't auto-raise if it's missing — let me
  handle that."
- `auto_error=False` is important: it lets us return a **custom error message**
  instead of FastAPI's generic 403.
- The function is used as a **FastAPI dependency**: any endpoint that needs
  API key auth adds `Depends(verify_api_key)` to its signature.
- The `code_agent` wires this into its A2A server.

**Security teaching moment:**

- The `!=` comparison is a plain string comparison — vulnerable to **timing
  attacks** in theory (an attacker could guess the key one character at a time
  by measuring response time).
- Production code should use `hmac.compare_digest()` for constant-time
  comparison. The code has a `TODO` comment noting this.
- This is a great example of "demo grade vs. production grade" — know the
  difference.

**How the code_agent uses it:**

```python
# In code_agent/agent.py
app = to_a2a(root_agent, agent_card=card)
app.add_middleware(...)  # or dependency injection via verify_api_key
```

---

### 3. Bearer JWT Authentication (lines 57–156)

This is the most complex section. Break it into two parts:

#### 3a. Token Creation (`create_bearer_token`, lines 62–99)

```python
def create_bearer_token(subject: str, ttl_seconds: int = 3600) -> str:
    header  = base64url({"alg": "HS256", "typ": "JWT"})
    payload = base64url({"sub": subject, "iat": now, "exp": now + ttl})
    signature = HMAC-SHA256(secret, f"{header}.{payload}")
    return f"{header}.{payload}.{signature}"
```

**Explain the three parts of a JWT to students:**

1. **Header** — metadata: algorithm (`HS256`) and type (`JWT`). Base64url-encoded.
2. **Payload** — claims: `sub` (subject/identity), `iat` (issued at), `exp`
   (expiry timestamp). Base64url-encoded.
3. **Signature** — HMAC-SHA256 of `header.payload` using a shared secret.
   This proves the token hasn't been tampered with.

**Key detail**: `.rstrip(b"=")` removes base64 padding. JWT spec says padding
is omitted (base64**url** encoding without padding).

**Teaching moment**: This is a hand-rolled JWT. In production, use `python-jose`,
`PyJWT`, or `authlib`. Hand-rolling crypto is educational but dangerous —
it's easy to introduce subtle bugs (e.g., algorithm confusion attacks, missing
claims validation).

#### 3b. Token Verification (`verify_bearer_token`, lines 102–156)

```python
def verify_bearer_token(credentials = Security(_http_bearer)) -> dict:
    # 1. Check scheme is "bearer"
    # 2. Split token into 3 parts
    # 3. Recompute signature, compare with hmac.compare_digest()
    # 4. Decode payload
    # 5. Check expiry
    return payload
```

**Walk through the verification steps:**

1. **Scheme check** (line 118): Ensure the `Authorization` header uses
   `Bearer` scheme, not `Basic` or something else.
2. **Structure check** (line 127): A JWT must have exactly 3 dot-separated parts.
3. **Signature verification** (lines 131–139):
   - Recompute the expected signature from `header.payload` + secret
   - Compare with `hmac.compare_digest()` — **constant-time comparison**
   - Note: this is done correctly here (unlike the API key check above)
4. **Payload decoding** (lines 142–144): Base64url-decode the middle part,
   parse as JSON.
5. **Expiry check** (line 147): Compare `exp` claim against current time.

**Security teaching moment:**

- The verification uses `hmac.compare_digest()` — this is **critical** for
  preventing timing attacks on the signature comparison.
- Adding `"=="` padding back (line 137) is needed because we stripped it during
  creation. `base64.urlsafe_b64decode` needs padding.
- A broad `except Exception` catches all failures and returns a generic 401.
  This is intentional — you don't want to leak information about *why* a
  token is invalid (was it expired? wrong signature? malformed?).

---

### 4. Webhook HMAC Verification (lines 159–184)

```python
def verify_webhook_signature(request_body: bytes, signature_header: str) -> bool:
    expected = hmac.new(WEBHOOK_AUTH_TOKEN, body, sha256).hexdigest()
    actual = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, actual)
```

**Explain to students:**

- This is the same pattern GitHub uses for webhook signatures.
- The sender (async agent) computes `HMAC-SHA256(shared_secret, request_body)`
  and sends it in the `X-Webhook-Signature: sha256=<hex>` header.
- The receiver (webhook server) recomputes the HMAC and compares.
- If they match, the payload is authentic and hasn't been tampered with.

**Why HMAC and not just a shared token?**

- A shared token in a header proves identity but doesn't prove the body
  hasn't been modified in transit.
- HMAC signs the **entire body** — if even one byte changes, the signature
  is invalid.
- `hmac.compare_digest()` prevents timing attacks.

**Teaching moment**: This is the "message authentication code" pattern. It
provides **integrity** (body hasn't been tampered with) and **authenticity**
(sender knows the secret). It does NOT provide **confidentiality** (the body
is not encrypted). For that, use HTTPS.

---

## Design Patterns to Highlight

1. **FastAPI Dependency Injection**: Auth functions are injected via
   `Security()` / `Depends()`. The endpoint code never touches headers
   directly — it just declares "I need an authenticated user" in its
   function signature.

2. **Defense in Depth**: Each agent chooses its own auth level based on risk.
   The weather agent (public data) is open; the code agent (runs code) requires
   an API key; the research agent (sensitive data) requires a JWT.

3. **Constant-Time Comparison**: `hmac.compare_digest()` prevents timing
   side-channel attacks. Always use it when comparing secrets.

4. **Fail Closed**: All auth functions raise exceptions on failure (HTTP 401/403).
   A missing or invalid credential never silently passes.

---

## Common Student Questions

1. **"Why not use OAuth 2.0 for everything?"** OAuth is complex — it involves
   token endpoints, scopes, refresh tokens, consent flows. For a demo, simpler
   schemes let us focus on A2A concepts. The data_agent does use real OAuth
   via GCP service accounts.

2. **"Is this JWT implementation secure?"** No. It's educational. Production
   issues: no `iss`/`aud` claims, no key rotation, no algorithm allow-listing.
   Use `python-jose` or `PyJWT` in production.

3. **"Why is `auto_error=False` used?"** So we can provide custom error messages
   and handle the "missing header" case ourselves, rather than getting FastAPI's
   default error response.

4. **"What's the difference between 401 and 403?"** 401 Unauthorized = "I don't
   know who you are" (missing/invalid credentials). 403 Forbidden = "I know
   who you are, but you're not allowed" (valid credentials, insufficient
   permissions).

---

## Related Files

- `shared/config.py` — Source of `CODE_AGENT_API_KEY`, `RESEARCH_AGENT_JWT_SECRET`,
  `WEBHOOK_AUTH_TOKEN`
- `code_agent/agent.py` — Wires in `verify_api_key` as a FastAPI dependency
- `research_agent/agent.py` — Wires in `verify_bearer_token`
- `webhook_server/main.py` — Calls `verify_webhook_signature`
- `clients/a2a_client.py` — Client-side: attaches API keys and Bearer tokens
  to outgoing requests
- `tests/test_shared_auth.py` — Tests for all auth functions
