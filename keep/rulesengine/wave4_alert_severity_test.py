import unittest

class TestWave4AlertSeverity(unittest.TestCase):
    def test_severity_escalation_rules(self):
        def compute_severity(error_rate: float, p99_latency_ms: float) -> str:
            if error_rate >= 0.10 or p99_latency_ms >= 5000:
                return 'critical'
            elif error_rate >= 0.02 or p99_latency_ms >= 1000:
                return 'warning'
            return 'info'

        self.assertEqual(compute_severity(0.001, 200), 'info')
        self.assertEqual(compute_severity(0.03, 400), 'warning')
        self.assertEqual(compute_severity(0.005, 1200), 'warning')
        self.assertEqual(compute_severity(0.15, 300), 'critical')
        self.assertEqual(compute_severity(0.01, 6000), 'critical')

    def test_alert_fingerprint_normalization(self):
        def generate_fingerprint(service: str, alert_name: str) -> str:
            return f"{service.lower().strip()}::{alert_name.lower().strip()}"

        self.assertEqual(generate_fingerprint("  API-Gateway  ", "High_5XX_Rate"), "api-gateway::high_5xx_rate")

if __name__ == '__main__':
    unittest.main()
