import unittest
import hashlib

class TestWave10AlertFingerprintNormalization(unittest.TestCase):
    def test_alert_fingerprint_generation(self):
        source = "prometheus"
        service = "payment-gateway"
        severity = "critical"

        raw_key = f"{source}:{service}:{severity}"
        fingerprint = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        self.assertEqual(len(fingerprint), 64)
        self.assertTrue(isinstance(fingerprint, str))

    def test_incident_grouping_window(self):
        window_seconds = 600 # 10 min window
        time_elapsed_secs = 450
        is_grouped = time_elapsed_secs <= window_seconds
        self.assertTrue(is_grouped)

if __name__ == '__main__':
    unittest.main()
