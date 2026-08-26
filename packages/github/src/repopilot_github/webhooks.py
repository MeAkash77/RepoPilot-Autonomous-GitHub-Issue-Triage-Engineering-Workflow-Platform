"""GitHub webhook signature verification.

Security boundary: every webhook request must carry a valid HMAC SHA-256
signature (X-Hub-Signature-256) computed over the raw body with the App's
webhook secret. Comparison is constant-time to prevent timing attacks.
"""

import hashlib
import hmac

SIGNATURE_PREFIX = "sha256="


def compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Return True iff signature_header matches the body HMAC. Never raises."""
    if not secret or not signature_header:
        return False
    if not signature_header.startswith(SIGNATURE_PREFIX):
        return False
    expected = compute_signature(secret, body)
    return hmac.compare_digest(expected, signature_header)


def payload_hash(body: bytes) -> str:
    """SHA-256 of the raw payload, stored in the idempotency ledger."""
    return hashlib.sha256(body).hexdigest()
