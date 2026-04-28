import unittest
from unittest.mock import MagicMock
from keep.providers.snmp_provider.snmp_provider import SNMPProvider

class TestSNMPProvider(unittest.TestCase):
    def test_sendSNMPTrap(self):
        config = {'host': 'localhost', 'community': 'public'}
        snmp = MagicMock()
        snmp.send_trap = MagicMock()

        provider = SNMPProvider(config)
        provider.snmp = snmp

        trap = {'oid': '1.3.6.1.4.1.9.9.41.1.3.1.1.6.1', 'value': 'test'}
        provider.sendSNMPTrap(trap)

        snmp.send_trap.assert_called_once_with(trap['oid'], trap['value'])

    def test_sendSNMPTrap_failure(self):
        config = {'host': 'localhost', 'community': 'public'}
        snmp = MagicMock()
        snmp.send_trap = MagicMock(side_effect=Exception("Mocked SNMP error"))

        provider = SNMPProvider(config)
        provider.snmp = snmp

        trap = {'oid': '1.3.6.1.4.1.9.9.41.1.3.1.1.6.1', 'value': 'test'}
        with self.assertRaises(Exception):
            provider.sendSNMPTrap(trap)