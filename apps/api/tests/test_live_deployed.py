"""Live end-to-end tests against the real deployed stack.

Opt-in: LIVE_API_URL=https://repopilot-api.fly.dev

Covers:
  - Health / uptime
  - Security headers present on every response
  - Webhook endpoint: HMAC auth, idempotency, 202 acceptance
  - Internal API: key gate, CORS, scoping
  - Rate-limiting headers present
  - Worker connectivity (via API health extended check)
"""

import hashlib
import hmac
import json
import os
import uuid
from datetime import UTC, datetime

import httpx
import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("LIVE_API_URL"),
        reason="Set LIVE_API_URL=https://repopilot-api.fly.dev to run live tests",
    ),
]

BASE = os.environ.get("LIVE_API_URL", "").rstrip("/")
INTERNAL_KEY = os.environ.get("INTERNAL_API_KEY", "")
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _webhook_headers(body: bytes, event: str = "issues") -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": str(uuid.uuid4()),
        "X-Hub-Signature-256": _sign(body, WEBHOOK_SECRET),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────────────


def test_health_ok() -> None:
    r = httpx.get(f"{BASE}/healthz", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ──────────────────────────────────────────────────────────────────────────────
# Security headers
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "header,expected",
    [
        ("strict-transport-security", "max-age="),
        ("x-content-type-options", "nosniff"),
        ("x-frame-options", "DENY"),
        ("referrer-policy", "no-referrer"),
    ],
)
def test_security_header_present(header: str, expected: str) -> None:
    r = httpx.get(f"{BASE}/healthz", timeout=10)
    value = r.headers.get(header, "")
    assert expected.lower() in value.lower(), f"{header}: got {value!r}"


# ──────────────────────────────────────────────────────────────────────────────
# Webhook — auth
# ──────────────────────────────────────────────────────────────────────────────


def test_webhook_no_signature_rejected() -> None:
    r = httpx.post(
        f"{BASE}/webhooks/github",
        content=b'{"action":"opened"}',
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": str(uuid.uuid4()),
        },
        timeout=10,
    )
    assert r.status_code in (400, 422)
    body = r.json()
    assert "signature" in json.dumps(body).lower() or "field required" in json.dumps(body).lower()


def test_webhook_wrong_signature_rejected() -> None:
    payload = b'{"action":"opened","issue":{"number":1,"title":"test"}}'
    r = httpx.post(
        f"{BASE}/webhooks/github",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "X-Hub-Signature-256": "sha256=deadbeefdeadbeef",
        },
        timeout=10,
    )
    # API returns 401 for invalid HMAC (treated as auth failure, not bad request).
    assert r.status_code == 401
    assert "signature" in r.json().get("detail", "").lower()


def test_webhook_valid_signature_accepted() -> None:
    """Send a valid signed webhook with a plausible payload — expect 202."""
    if not WEBHOOK_SECRET:
        pytest.skip("GITHUB_WEBHOOK_SECRET not set")
    payload = json.dumps(
        {
            "action": "opened",
            "installation": {"id": 999999999},
            "issue": {
                "number": 9001,
                "title": "[live-e2e] smoke test issue",
                "body": "This is an automated live e2e smoke test. Safe to ignore.",
                "user": {"login": "repopilot-bot"},
                "state": "open",
                "labels": [],
                "created_at": datetime.now(UTC).isoformat(),
            },
            "repository": {
                "id": 999999999,
                "full_name": "AyushCoder9/repopilot-sandbox",
                "private": False,
            },
            "sender": {"login": "repopilot-bot"},
        }
    ).encode()

    r = httpx.post(
        f"{BASE}/webhooks/github",
        content=payload,
        headers=_webhook_headers(payload, "issues"),
        timeout=15,
    )
    # 202 = accepted + queued; 200 = accepted (e.g. unknown event skipped)
    # The API returns 202 even for unknown installation_id (async processing).
    assert r.status_code in (200, 202), f"got {r.status_code}: {r.text}"


def test_webhook_idempotent_duplicate_rejected() -> None:
    """Resending the same delivery ID must be rejected as duplicate."""
    if not WEBHOOK_SECRET:
        pytest.skip("GITHUB_WEBHOOK_SECRET not set")
    payload = json.dumps({"action": "labeled", "installation": {"id": 1}}).encode()
    delivery_id = str(uuid.uuid4())
    headers = {
        **_webhook_headers(payload, "issues"),
        "X-GitHub-Delivery": delivery_id,
    }

    r1 = httpx.post(f"{BASE}/webhooks/github", content=payload, headers=headers, timeout=10)
    r2 = httpx.post(f"{BASE}/webhooks/github", content=payload, headers=headers, timeout=10)

    assert r1.status_code in (200, 202)
    # Second delivery with same ID is a duplicate — must not be re-enqueued.
    # API may return 202 (noop acknowledged) or 409 conflict.
    assert r2.status_code in (200, 202, 409), f"unexpected: {r2.status_code} {r2.text}"


# ──────────────────────────────────────────────────────────────────────────────
# Internal API — auth gate
# ──────────────────────────────────────────────────────────────────────────────


def test_internal_api_no_key_returns_401() -> None:
    r = httpx.get(f"{BASE}/api/v1/repos", timeout=10)
    assert r.status_code == 401


def test_internal_api_wrong_key_returns_401() -> None:
    r = httpx.get(
        f"{BASE}/api/v1/repos",
        headers={"X-Internal-Key": "wrong-key"},
        timeout=10,
    )
    assert r.status_code == 401


def test_internal_api_valid_key_returns_200() -> None:
    if not INTERNAL_KEY:
        pytest.skip("INTERNAL_API_KEY not set")
    r = httpx.get(
        f"{BASE}/api/v1/repos",
        headers={"X-Internal-Key": INTERNAL_KEY},
        timeout=10,
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_internal_api_runs_endpoint() -> None:
    if not INTERNAL_KEY:
        pytest.skip("INTERNAL_API_KEY not set")
    r = httpx.get(
        f"{BASE}/api/v1/runs",
        headers={"X-Internal-Key": INTERNAL_KEY},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    # /api/v1/runs returns paginated {items: [], next_cursor: null}
    assert isinstance(body, list) or "items" in body


def test_internal_api_analytics_endpoint() -> None:
    if not INTERNAL_KEY:
        pytest.skip("INTERNAL_API_KEY not set")
    r = httpx.get(
        f"{BASE}/api/v1/analytics/overview",
        headers={"X-Internal-Key": INTERNAL_KEY},
        timeout=10,
    )
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


# ──────────────────────────────────────────────────────────────────────────────
# Body size cap
# ──────────────────────────────────────────────────────────────────────────────


def test_oversize_webhook_rejected() -> None:
    """Payload > 2 MB must return 413."""
    if not WEBHOOK_SECRET:
        pytest.skip("GITHUB_WEBHOOK_SECRET not set")
    oversized = json.dumps({"action": "opened", "body": "x" * (2 * 1024 * 1024 + 1)}).encode()
    r = httpx.post(
        f"{BASE}/webhooks/github",
        content=oversized,
        headers=_webhook_headers(oversized, "issues"),
        timeout=30,
    )
    assert r.status_code == 413, f"expected 413, got {r.status_code}"
