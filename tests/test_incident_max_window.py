from datetime import datetime, timedelta

from keep.api.utils.incident_expiry import compute_incident_expired

NOW = datetime(2024, 1, 1, 12, 0, 0)


def test_terminal_status_is_expired():
    assert compute_incident_expired(True, None, NOW, 3600, None, NOW) is True


def test_no_max_window_within_timeframe_not_expired():
    latest = NOW - timedelta(seconds=60)
    creation = NOW - timedelta(hours=5)
    assert compute_incident_expired(False, latest, creation, 3600, None, NOW) is False


def test_no_max_window_older_than_timeframe_expired():
    latest = NOW - timedelta(seconds=7200)
    creation = NOW - timedelta(hours=5)
    assert compute_incident_expired(False, latest, creation, 3600, None, NOW) is True


def test_no_alerts_not_expired():
    assert compute_incident_expired(False, None, NOW, 3600, None, NOW) is False


def test_max_window_locks_incident_even_within_timeframe():
    latest = NOW - timedelta(seconds=60)
    creation = NOW - timedelta(seconds=7200)
    assert compute_incident_expired(False, latest, creation, 3600, 3600, NOW) is True


def test_within_max_window_not_expired():
    latest = NOW - timedelta(seconds=60)
    creation = NOW - timedelta(seconds=1800)
    assert compute_incident_expired(False, latest, creation, 3600, 3600, NOW) is False


def test_max_window_boundary_exact_not_expired():
    creation = NOW - timedelta(seconds=3600)
    latest = NOW - timedelta(seconds=60)
    assert compute_incident_expired(False, latest, creation, 3600, 3600, NOW) is False
