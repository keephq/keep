import unittest

class TestWave12IncidentSLATimer(unittest.TestCase):
    def test_sla_breach_detection(self):
        critical_sla_seconds = 900 # 15 minutes
        
        def is_sla_breached(elapsed_seconds: int, max_sla: int) -> bool:
            return elapsed_seconds > max_sla

        self.assertFalse(is_sla_breached(600, critical_sla_seconds))
        self.assertTrue(is_sla_breached(950, critical_sla_seconds))

    def test_alert_noise_reduction_ratio(self):
        def calculate_noise_reduction(raw_alerts: int, grouped_incidents: int) -> float:
            if raw_alerts == 0:
                return 0.0
            return ((raw_alerts - grouped_incidents) / raw_alerts) * 100.0

        reduction = calculate_noise_reduction(100, 10)
        self.assertEqual(reduction, 90.0)

if __name__ == '__main__':
    unittest.main()
