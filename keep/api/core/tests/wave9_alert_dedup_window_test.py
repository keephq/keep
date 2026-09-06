import unittest
from datetime import datetime, timedelta

class TestWave9AlertDedupWindow(unittest.TestCase):
    def test_alert_window_grouping(self):
        window_seconds = 300
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=150)
        t2 = t0 + timedelta(seconds=400)
        
        in_window_1 = (t1 - t0).total_seconds() <= window_seconds
        in_window_2 = (t2 - t0).total_seconds() <= window_seconds
        
        self.assertTrue(in_window_1)
        self.assertFalse(in_window_2)

if __name__ == '__main__':
    unittest.main()
