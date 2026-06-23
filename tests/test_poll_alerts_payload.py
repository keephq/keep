from keep.api.consts import FINGERPRINT_PAYLOAD_LIMIT, fingerprints_for_poll_payload


def test_fingerprints_for_poll_payload_within_limit():
    fingerprints = [f"fp-{index}" for index in range(FINGERPRINT_PAYLOAD_LIMIT)]
    assert fingerprints_for_poll_payload(fingerprints) == fingerprints


def test_fingerprints_for_poll_payload_above_limit_returns_empty():
    fingerprints = [f"fp-{index}" for index in range(FINGERPRINT_PAYLOAD_LIMIT + 1)]
    assert fingerprints_for_poll_payload(fingerprints) == []
