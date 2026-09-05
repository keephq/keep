# Wave 2 Test Suite: Alert Severity Normalization & Rule Invariant Specs

def test_wave2_severity_normalization():
    valid_severities = {"critical", "high", "medium", "low", "info"}
    
    def normalize_severity(sev: str) -> str:
        s = (sev or "").strip().lower()
        return s if s in valid_severities else "info"

    assert normalize_severity("CRITICAL") == "critical"
    assert normalize_severity(" High ") == "high"
    assert normalize_severity("unknown_severity") == "info"
    assert normalize_severity("") == "info"

def test_wave2_rule_timeout_bounds():
    MAX_TIMEOUT_SECONDS = 3600
    MIN_TIMEOUT_SECONDS = 5

    def clamp_timeout(t: int) -> int:
        return max(MIN_TIMEOUT_SECONDS, min(t, MAX_TIMEOUT_SECONDS))

    assert clamp_timeout(0) == 5
    assert clamp_timeout(120) == 120
    assert clamp_timeout(7200) == 3600
