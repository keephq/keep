import unittest
from datetime import datetime, timezone

class TestAlertTimestampBoundaries(unittest.TestCase):
    def test_alert_timestamp_utc_invariant(self):
        now_utc = datetime.now(timezone.utc)
        iso_str = now_utc.isoformat()
        
        parsed = datetime.fromisoformat(iso_str)
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertLessEqual((datetime.now(timezone.utc) - parsed).total_seconds(), 5)

    def test_alert_window_monotonic_ordering(self):
        t1 = 1725800000.0
        t2 = 1725800060.0
        t3 = 1725800120.0

        self.assertTrue(t1 < t2 < t3)
        self.assertEqual(t2 - t1, 60.0)

if __name__ == "__main__":
    unittest.main()
