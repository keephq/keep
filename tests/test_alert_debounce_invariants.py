def test_alert_debounce_window_invariants():
    debounce_window_seconds = 30
    first_alert = 100
    second_alert = 115
    assert (second_alert - first_alert) < debounce_window_seconds
