import pytest
from datetime import datetime, timedelta

def test_alert_fingerprint_deduplication():
    def compute_alert_fingerprint(source: str, service: str, rule: str) -> str:
        import hashlib
        raw = f"{source.strip().lower()}:{service.strip().lower()}:{rule.strip().lower()}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    fp1 = compute_alert_fingerprint("prometheus", "auth-service", "HighLatency")
    fp2 = compute_alert_fingerprint("Prometheus ", "AUTH-SERVICE", "highlatency")
    fp3 = compute_alert_fingerprint("datadog", "auth-service", "HighLatency")

    assert fp1 == fp2
    assert fp1 != fp3

def test_alert_throttle_window_evaluation():
    def is_throttled(last_sent_at: datetime, current_at: datetime, window_seconds: int = 300) -> bool:
        if not last_sent_at:
            return False
        return (current_at - last_sent_at).total_seconds() < window_seconds

    now = datetime.utcnow()
    assert is_throttled(now - timedelta(seconds=120), now, 300) is True
    assert is_throttled(now - timedelta(seconds=301), now, 300) is False
    assert is_throttled(None, now, 300) is False
