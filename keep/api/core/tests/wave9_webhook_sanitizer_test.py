import unittest

class TestWave9WebhookPayloadSanitizer(unittest.TestCase):
    def test_sensitive_header_masking(self):
        headers = {
            "Authorization": "Bearer secret_api_token_12345",
            "X-Api-Key": "live_key_999",
            "Content-Type": "application/json"
        }

        sensitive_keys = {"authorization", "x-api-key", "token", "password"}

        def sanitize_headers(hdrs: dict) -> dict:
            return {
                k: ("***MASKED***" if k.lower() in sensitive_keys else v)
                for k, v in hdrs.items()
            }

        sanitized = sanitize_headers(headers)
        self.assertEqual(sanitized["Authorization"], "***MASKED***")
        self.assertEqual(sanitized["X-Api-Key"], "***MASKED***")
        self.assertEqual(sanitized["Content-Type"], "application/json")

    def test_alert_severity_canonical_mapping(self):
        severity_map = {
            "critical": "CRITICAL",
            "high": "HIGH",
            "warn": "WARNING",
            "warning": "WARNING",
            "info": "INFO"
        }
        self.assertEqual(severity_map.get("warn"), "WARNING")
        self.assertEqual(severity_map.get("critical"), "CRITICAL")

if __name__ == '__main__':
    unittest.main()
