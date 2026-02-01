import pytest
from unittest.mock import MagicMock, patch
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.providers.models.provider_config import ProviderConfig

@pytest.fixture
def snmp_provider():
    config = ProviderConfig(
        authentication={
            "v3_user": "keep-user",
            "v3_auth_key": "keep-auth-key",
            "v3_priv_key": "keep-priv-key",
            "v3_auth_protocol": "sha",
            "v3_priv_protocol": "aes"
        }
    )
    return SnmpProvider(provider_id="snmp-test", config=config)

def test_snmp_v3_auth_parsing(snmp_provider):
    # Test v3 authentication configuration parsing
    auth_data = snmp_provider._parse_v3_auth()
    assert auth_data["userName"] == "keep-user"
    assert auth_data["authKey"] == "keep-auth-key"
    assert auth_data["privKey"] == "keep-priv-key"
    assert auth_data["authProtocol"] == "sha"
    assert auth_data["privProtocol"] == "aes"

def test_snmp_v2c_auth_parsing():
    config = ProviderConfig(
        authentication={
            "community": "public",
            "version": "2c"
        }
    )
    provider = SnmpProvider(provider_id="snmp-v2c", config=config)
    assert provider.config.authentication.get("community") == "public"
    assert provider.config.authentication.get("version") == "2c"

@patch("keep.providers.snmp_provider.snmp_provider.hlapi")
def test_snmp_notify_trap_parsing(mock_hlapi, snmp_provider):
    # 1. Mock the 'pysnmp' library (hlapi.v3asynciodispatcher) to simulate receiving a Trap
    mock_dispatcher = MagicMock()
    mock_hlapi.v3asynciodispatcher.AsynioDispatcher.return_value = mock_dispatcher
    
    # Simulate trap data
    # In pysnmp, varBinds is a list of (OID, Value) tuples
    mock_var_binds = [
        ("1.3.6.1.2.1.1.3.0", MagicMock(prettyPrint=lambda: "12345")),  # sysUpTime
        ("1.3.6.1.6.3.1.1.4.1.0", MagicMock(prettyPrint=lambda: "1.3.6.1.4.1.2021.251.1")),  # snmpTrapOID
        ("1.3.6.1.4.1.2021.11.101.0", MagicMock(prettyPrint=lambda: "Critical CPU usage detected")) # Custom OID
    ]
    
    # 2. Verify that 'notify' correctly parses the trap and converts it into a Keep Alert
    # We mock the internal callback or the way notify processes incoming data
    # Assuming SnmpProvider has a method to process raw var_binds into an alert
    alert = snmp_provider._process_trap(mock_var_binds, "127.0.0.1")
    
    assert alert["source"] == "snmp"
    assert alert["host"] == "127.0.0.1"
    assert "Critical CPU usage detected" in str(alert["event"])
    assert alert["trap_oid"] == "1.3.6.1.4.1.2021.251.1"

def test_snmp_v1_config_parsing():
    config = ProviderConfig(
        authentication={
            "community": "private",
            "version": "1"
        }
    )
    provider = SnmpProvider(provider_id="snmp-v1", config=config)
    assert provider.config.authentication.get("community") == "private"
    assert provider.config.authentication.get("version") == "1"
