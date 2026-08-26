from repopilot_github.webhooks import compute_signature, payload_hash, verify_signature

SECRET = "test-secret"
BODY = b'{"action": "opened"}'


def test_valid_signature_accepted() -> None:
    sig = compute_signature(SECRET, BODY)
    assert verify_signature(SECRET, BODY, sig)


def test_tampered_body_rejected() -> None:
    sig = compute_signature(SECRET, BODY)
    assert not verify_signature(SECRET, b'{"action": "closed"}', sig)


def test_wrong_secret_rejected() -> None:
    sig = compute_signature("other-secret", BODY)
    assert not verify_signature(SECRET, BODY, sig)


def test_missing_header_rejected() -> None:
    assert not verify_signature(SECRET, BODY, None)
    assert not verify_signature(SECRET, BODY, "")


def test_malformed_header_rejected() -> None:
    assert not verify_signature(SECRET, BODY, "sha1=abcdef")
    assert not verify_signature(SECRET, BODY, "garbage")


def test_empty_secret_rejected() -> None:
    sig = compute_signature("", BODY)
    assert not verify_signature("", BODY, sig)


def test_payload_hash_is_sha256_hex() -> None:
    digest = payload_hash(BODY)
    assert len(digest) == 64
    assert digest == payload_hash(BODY)
