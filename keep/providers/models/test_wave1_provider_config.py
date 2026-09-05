import unittest

class TestProviderConfigValidation(unittest.TestCase):
    def test_provider_name_normalization(self):
        def normalize_provider(name: str) -> str:
            return name.strip().lower().replace(" ", "_")
        
        self.assertEqual(normalize_provider(" Datadog "), "datadog")
        self.assertEqual(normalize_provider("AWS CloudWatch"), "aws_cloudwatch")
        self.assertEqual(normalize_provider("PagerDuty"), "pagerduty")

    def test_provider_auth_scope_defaults(self):
        auth_config = {"api_key": "secret_key_123", "scopes": ["alerts:read", "alerts:write"]}
        self.assertTrue("alerts:read" in auth_config["scopes"])
        self.assertEqual(len(auth_config["scopes"]), 2)

if __name__ == '__main__':
    unittest.main()
