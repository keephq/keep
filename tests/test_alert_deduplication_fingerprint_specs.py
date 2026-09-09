import unittest
import hashlib

class TestAlertDeduplicationFingerprint(unittest.TestCase):
    def test_alert_fingerprint_generation_invariants(self):
        service = "payment-gateway"
        error_code = "ERR_GATEWAY_TIMEOUT"
        env = "production"

        payload1 = f"{service}:{error_code}:{env}".encode('utf-8')
        fingerprint1 = hashlib.sha256(payload1).hexdigest()

        payload2 = f"{service}:{error_code}:{env}".encode('utf-8')
        fingerprint2 = hashlib.sha256(payload2).hexdigest()

        self.assertEqual(fingerprint1, fingerprint2)
        self.assertEqual(len(fingerprint1), 64)

    def test_alert_fingerprint_distinctness_across_environments(self):
        service = "payment-gateway"
        error_code = "ERR_GATEWAY_TIMEOUT"

        prod_hash = hashlib.sha256(f"{service}:{error_code}:production".encode('utf-8')).hexdigest()
        staging_hash = hashlib.sha256(f"{service}:{error_code}:staging".encode('utf-8')).hexdigest()

        self.assertNotEqual(prod_hash, staging_hash)

if __name__ == "__main__":
    unittest.main()
