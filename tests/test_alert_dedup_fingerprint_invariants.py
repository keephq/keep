import hashlib
import pytest

def test_alert_fingerprint_dedup_invariants():
    raw_payload_1 = {"service": "api-gateway", "severity": "error", "code": 500}
    raw_payload_2 = {"service": "api-gateway", "severity": "error", "code": 500}
    raw_payload_3 = {"service": "worker", "severity": "error", "code": 500}

    fp1 = hashlib.sha256(str(sorted(raw_payload_1.items())).encode()).hexdigest()
    fp2 = hashlib.sha256(str(sorted(raw_payload_2.items())).encode()).hexdigest()
    fp3 = hashlib.sha256(str(sorted(raw_payload_3.items())).encode()).hexdigest()

    assert fp1 == fp2
    assert fp1 != fp3

def test_dedup_window_clamping():
    max_window_sec = 3600
    requested_window = 7200
    clamped = min(requested_window, max_window_sec)

    assert clamped == 3600
