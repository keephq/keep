import unittest
from unittest.mock import MagicMock
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.contextmanager.contextmanager import ContextManager

class TestSnmpProvider(unittest.TestCase):
    def setUp(self):
        self.context_manager = ContextManager(tenant_id="test-tenant")
        self.config = ProviderConfig(
            authentication={
                "bind_address": "127.0.0.1",
                "port": 1162,
                "community": "public",
            }
        )
        self.provider = SnmpProvider(
            context_manager=self.context_manager,
            provider_id="snmp-test",
            config=self.config
        )

    def test_initialization(self):
        self.assertEqual(self.provider.provider_id, "snmp-test")
        self.assertEqual(self.provider.authentication_config.port, 1162)

    def test_status(self):
        status = self.provider.status()
        self.assertEqual(status["status"], "stopped")

if __name__ == "__main__":
    unittest.main()
