import unittest

class TestWave5AlertDebounce(unittest.TestCase):
    def test_alert_debounce_window_filtering(self):
        def should_suppress_alert(last_fired_ts: int, current_ts: int, debounce_window_sec: int) -> bool:
            return (current_ts - last_fired_ts) < debounce_window_sec

        self.assertTrue(should_suppress_alert(1000, 1030, 60))
        self.assertFalse(should_suppress_alert(1000, 1070, 60))
        self.assertFalse(should_suppress_alert(1000, 1060, 60))

    def test_alert_severity_weight_ordering(self):
        severity_weights = {'info': 1, 'warning': 2, 'critical': 3}
        self.assertGreater(severity_weights['critical'], severity_weights['warning'])
        self.assertGreater(severity_weights['warning'], severity_weights['info'])

if __name__ == '__main__':
    unittest.main()
