import unittest

class TestWave7IncidentCorrelation(unittest.TestCase):
    def test_fingerprint_generation(self):
        def generate_alert_fingerprint(service: str, alert_name: str, environment: str) -> str:
            return f"{environment.lower()}::{service.lower()}::{alert_name.lower()}"

        fp1 = generate_alert_fingerprint("Auth-Service", "HighErrorRate", "Production")
        self.assertEqual(fp1, "production::auth-service::higherrorrate")

    def test_incident_grouping_window(self):
        def can_group_with_incident(incident_start_ts: int, alert_ts: int, max_window_sec: int) -> bool:
            return (alert_ts - incident_start_ts) >= 0 and (alert_ts - incident_start_ts) <= max_window_sec

        self.assertTrue(can_group_with_incident(1000, 1120, 300))
        self.assertFalse(can_group_with_incident(1000, 1350, 300))
        self.assertFalse(can_group_with_incident(1000, 950, 300))

if __name__ == '__main__':
    unittest.main()
