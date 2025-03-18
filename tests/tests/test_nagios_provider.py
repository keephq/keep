import unittest
from unittest.mock import patch
from providers.nagios_provider import NagiosProvider

class TestNagiosProvider(unittest.TestCase):
    def setUp(self):
        """
        Set up a mock NagiosProvider instance for testing.
        """
        self.provider = NagiosProvider(base_url="http://example.com", api_key="test_key")

    @patch("providers.nagios_provider.NagiosProvider.fetch_alerts")
    def test_fetch_alerts(self, mock_fetch_alerts):
        """
        Test the fetch_alerts method.
        """
        # Mock the response
        mock_fetch_alerts.return_value = [{"alert": "Test Alert"}]

        # Call the method
        alerts = self.provider.fetch_alerts()

        # Assert the result
        self.assertIsNotNone(alerts)
        self.assertEqual(alerts, [{"alert": "Test Alert"}])

if __name__ == "__main__":
    unittest.main()