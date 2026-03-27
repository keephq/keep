import unittest
from unittest.mock import MagicMock, patch
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.models.provider_config import ProviderConfig

class TestSnmpProvider(unittest.TestCase):
    def setUp(self):
        self.config = ProviderConfig(
            authentication={
                "host": "127.0.0.1",
                "port": 161,
                "community": "public",
                "version": "v2c"
            }
        )
        self.provider = SnmpProvider("test-snmp", self.config)

    def test_validate_config(self):
        self.provider.validate_config()
        self.assertEqual(self.provider.host, "127.0.0.1")
        self.assertEqual(self.provider.port, 161)

    @patch("keep.providers.snmp_provider.snmp_provider.getCmd")
    def test_query_success(self, mock_getCmd):
        # Mocking SNMP response
        mock_iterator = MagicMock()
        mock_iterator.__next__.return_value = (None, 0, 0, [("1.3.6.1.2.1.1.1.0", "System Description")])
        mock_getCmd.return_value = mock_iterator

        result = self.provider.query(oid="1.3.6.1.2.1.1.1.0")
        self.assertIn("1.3.6.1.2.1.1.1.0", result)
        self.assertEqual(result["1.3.6.1.2.1.1.1.0"], "System Description")

if __name__ == "__main__":
    unittest.main()
  
