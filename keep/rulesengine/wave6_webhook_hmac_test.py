import unittest
import hmac
import hashlib

class TestWave6WebhookHMAC(unittest.TestCase):
    def test_webhook_signature_verification(self):
        secret = b"keep_secret_key_2026"
        payload = b'{"event":"alert_fired","severity":"critical","service":"db-cluster"}'
        
        expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        
        def verify_signature(sec: bytes, body: bytes, sig: str) -> bool:
            computed = hmac.new(sec, body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(computed, sig)

        self.assertTrue(verify_signature(secret, payload, expected_sig))
        self.assertFalse(verify_signature(b"wrong_secret", payload, expected_sig))
        self.assertFalse(verify_signature(secret, b'tampered_body', expected_sig))

    def test_webhook_timestamp_replay_prevention(self):
        def is_timestamp_fresh(received_ts: int, current_ts: int, max_drift_sec: int) -> bool:
            return abs(current_ts - received_ts) <= max_drift_sec

        self.assertTrue(is_timestamp_fresh(1000, 1020, 60))
        self.assertFalse(is_timestamp_fresh(1000, 1100, 60))

if __name__ == '__main__':
    unittest.main()
