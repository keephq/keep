#!/usr/bin/env python3
"""
Standalone test runner for SNMP and SolarWinds providers.
Tests _format_alert() in isolation without importing the full Keep stack.
"""

import sys
import os

# Mock the Keep imports
class MockSeverity:
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    INFO = "info"

class MockStatus:
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"

class MockAlertDto:
    def __init__(self, **kwargs):
        self.data = kwargs
    def __repr__(self):
        return f"AlertDto({self.data})"

# Inject mocks
sys.modules['keep'] = type(sys)('keep')
sys.modules['keep.api'] = type(sys)('keep.api')
sys.modules['keep.api.models'] = type(sys)('keep.api.models')
sys.modules['keep.api.models.alert'] = type(sys)('keep.api.models.alert')
sys.modules['keep.api.models.alert'].AlertDto = MockAlertDto
sys.modules['keep.api.models.alert'].AlertSeverity = MockSeverity
sys.modules['keep.api.models.alert'].AlertStatus = MockStatus

sys.modules['keep.contextmanager'] = type(sys)('keep.contextmanager')
sys.modules['keep.contextmanager'].contextmanager = type(sys)('keep.contextmanager.contextmanager')
sys.modules['keep.contextmanager'].ContextManager = object

sys.modules['keep.providers'] = type(sys)('keep.providers')
sys.modules['keep.providers.base'] = type(sys)('keep.providers.base')
sys.modules['keep.providers.base'].base_provider = type(sys)('keep.providers.base.base_provider')
sys.modules['keep.providers.base'].base_provider.BaseProvider = object

sys.modules['keep.providers.models'] = type(sys)('keep.providers.models')
sys.modules['keep.providers.models'].provider_config = type(sys)('keep.providers.models.provider_config')
sys.modules['keep.providers.models'].provider_config.ProviderConfig = object

# Now import and test
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.providers.solarwinds_provider.solarwinds_provider import SolarwindsProvider

def test_snmp():
    print("Testing SNMP Provider...")

    # Test 1: v2c linkDown
    result = SnmpProvider._format_alert({
        "version": "v2c",
        "oid": "1.3.6.1.6.3.1.1.5.3",
        "agent_address": "192.168.1.100",
        "hostname": "switch01.example.com",
        "description": "Interface down",
    })
    assert result.data['severity'] == MockSeverity.CRITICAL
    assert result.data['status'] == MockStatus.FIRING
    assert result.data['host'] == "switch01.example.com"
    assert result.data['source'] == ["snmp"]
    print("  ✅ v2c linkDown → CRITICAL/FIRING")

    # Test 2: v1 linkUp (should resolve)
    result = SnmpProvider._format_alert({
        "version": "v1",
        "generic_trap": 3,
        "agent_address": "10.0.0.1",
        "hostname": "router01",
    })
    assert result.data['status'] == MockStatus.RESOLVED
    assert result.data['severity'] == MockSeverity.INFO
    print("  ✅ v1 linkUp → RESOLVED/INFO")

    # Test 3: Custom severity override
    result = SnmpProvider._format_alert({
        "version": "v2c",
        "oid": "1.3.6.1.6.3.1.1.5.1",
        "severity": "major",
        "hostname": "firewall01",
    })
    assert result.data['severity'] == MockSeverity.HIGH
    print("  ✅ Custom severity 'major' → HIGH")

    # Test 4: Integer severity doesn't crash
    result = SnmpProvider._format_alert({
        "version": "v2c",
        "oid": "1.3.6.1.6.3.1.1.5.3",
        "severity": 5,  # int, not string
        "hostname": "switch01",
    })
    # Should default to WARNING since "5" isn't in our map
    assert result.data['severity'] == MockSeverity.WARNING
    print("  ✅ Integer severity doesn't crash")

    # Test 5: Empty event doesn't crash
    result = SnmpProvider._format_alert({})
    assert result is not None
    print("  ✅ Empty event doesn't crash")

    print("\nAll SNMP tests passed! ✅\n")

def test_solarwinds():
    print("Testing SolarWinds Provider...")

    # Test 1: Node Down (Severity 2)
    result = SolarwindsProvider._format_alert({
        "AlertName": "Node Down",
        "AlertActiveID": "8819",
        "Severity": 2,
        "Acknowledged": False,
        "NodeName": "core-sw-01.example.com",
        "TimeOfAlert": "2024-06-12T14:32:07+00:00",
    })
    assert result.data['severity'] == MockSeverity.CRITICAL
    assert result.data['status'] == MockStatus.FIRING
    assert result.data['host'] == "core-sw-01.example.com"
    assert result.data['id'] == "8819"
    assert result.data['source'] == ["solarwinds"]
    print("  ✅ Node Down (Severity 2) → CRITICAL/FIRING")

    # Test 2: High CPU (Severity 1)
    result = SolarwindsProvider._format_alert({
        "AlertName": "High CPU Load",
        "AlertActiveID": "9203",
        "Severity": 1,
        "Acknowledged": False,
    })
    assert result.data['severity'] == MockSeverity.WARNING
    print("  ✅ High CPU (Severity 1) → WARNING")

    # Test 3: String Acknowledged
    result = SolarwindsProvider._format_alert({
        "AlertName": "Disk Full",
        "AlertActiveID": "9700",
        "Severity": 3,
        "Acknowledged": "True",
    })
    assert result.data['status'] == MockStatus.ACKNOWLEDGED
    print("  ✅ String Acknowledged='True' → ACKNOWLEDGED")

    # Test 4: String severity as int
    result = SolarwindsProvider._format_alert({
        "AlertName": "Interface Down",
        "AlertActiveID": "9815",
        "Severity": "1",
        "Acknowledged": False,
    })
    assert result.data['severity'] == MockSeverity.WARNING
    print("  ✅ String Severity='1' → WARNING")

    # Test 5: Named string severity
    result = SolarwindsProvider._format_alert({
        "AlertName": "Auth Failure",
        "AlertActiveID": "9999",
        "Severity": "critical",
        "Acknowledged": False,
    })
    assert result.data['severity'] == MockSeverity.CRITICAL
    print("  ✅ Named Severity='critical' → CRITICAL")

    # Test 6: Reset status
    result = SolarwindsProvider._format_alert({
        "AlertName": "Resolved Alert",
        "AlertActiveID": "0001",
        "Severity": 2,
        "AlertStatus": "Reset",
    })
    assert result.data['status'] == MockStatus.RESOLVED
    print("  ✅ AlertStatus='Reset' → RESOLVED")

    # Test 7: IP_Address flows through
    result = SolarwindsProvider._format_alert({
        "AlertName": "Test",
        "AlertActiveID": "0002",
        "Severity": 1,
        "IP_Address": "10.0.1.1",
    })
    assert 'IP_Address' in result.data
    assert result.data['IP_Address'] == "10.0.1.1"
    print("  ✅ IP_Address flows through to AlertDto")

    # Test 8: Empty event doesn't crash
    result = SolarwindsProvider._format_alert({})
    assert result is not None
    print("  ✅ Empty event doesn't crash")

    print("\nAll SolarWinds tests passed! ✅\n")

if __name__ == "__main__":
    test_snmp()
    test_solarwinds()
    print("=" * 50)
    print("ALL TESTS PASSED! 🎉")
    print("=" * 50)
