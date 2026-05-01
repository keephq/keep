import pytest
from unittest.mock import MagicMock


@pytest.fixture
def snmp_provider():
    from keep.contextmanager.contextmanager import ContextManager
    from keep.providers.models.provider_config import ProviderConfig
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    context_manager = ContextManager(
        tenant_id="test-tenant",
        workflow_id="test",
    )
    # validate_config() is called inside BaseProvider.__init__ via super().__init__()
    # authentication_config is therefore available immediately after construction
    config = ProviderConfig(authentication={})
    return SnmpProvider(context_manager, "test-snmp", config)


def test_validate_config_uses_defaults(snmp_provider):
    """Provider initializes with correct default configuration values."""
    assert snmp_provider.authentication_config.listen_port == 1162
    assert snmp_provider.authentication_config.community_string == "public"
    assert snmp_provider.authentication_config.listen_address == "0.0.0.0"


def test_validate_config_respects_custom_values():
    """Provider stores custom configuration values correctly."""
    from keep.contextmanager.contextmanager import ContextManager
    from keep.providers.models.provider_config import ProviderConfig
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    context_manager = ContextManager(
        tenant_id="test-tenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        authentication={"listen_port": 10162, "community_string": "private"}
    )
    provider = SnmpProvider(context_manager, "test-snmp-custom", config)
    assert provider.authentication_config.listen_port == 10162
    assert provider.authentication_config.community_string == "private"


def test_parse_trap_extracts_trap_oid(snmp_provider):
    """_parse_trap correctly extracts snmpTrapOID.0 value from var_binds."""
    mock_engine = MagicMock()
    mock_engine.msgAndPduDsp.getTransportInfo.return_value = (
        None,
        ("192.168.1.10", 161),
    )

    # snmpTrapOID.0 entry
    trap_oid_oid = MagicMock()
    trap_oid_oid.__str__ = lambda self: "1.3.6.1.6.3.1.1.4.1.0"
    trap_oid_val = MagicMock()
    trap_oid_val.__str__ = lambda self: "1.3.6.1.6.3.1.1.5.3"

    # Additional OID entry
    other_oid = MagicMock()
    other_oid.__str__ = lambda self: "1.3.6.1.2.1.1.3.0"
    other_val = MagicMock()
    other_val.__str__ = lambda self: "12345"

    var_binds = [(trap_oid_oid, trap_oid_val), (other_oid, other_val)]
    result = snmp_provider._parse_trap(var_binds, mock_engine, MagicMock())

    assert result["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"
    assert result["source"] == ["snmp"]
    assert result["source_address"] == "192.168.1.10"
    assert result["severity"] == "info"
    assert "lastReceived" in result
    assert "id" in result


def test_parse_trap_missing_trap_oid_does_not_raise(snmp_provider):
    """_parse_trap handles var_binds with no snmpTrapOID.0 entry gracefully."""
    mock_engine = MagicMock()
    mock_engine.msgAndPduDsp.getTransportInfo.return_value = (
        None, ("10.0.0.1", 161)
    )

    other_oid = MagicMock()
    other_oid.__str__ = lambda self: "1.3.6.1.2.1.1.1.0"
    other_val = MagicMock()
    other_val.__str__ = lambda self: "some-value"

    result = snmp_provider._parse_trap(
        [(other_oid, other_val)], mock_engine, MagicMock()
    )

    assert result["trap_oid"] == "unknown"
    assert result["source"] == ["snmp"]


def test_is_consumer_returns_true(snmp_provider):
    """Keep correctly identifies SnmpProvider as a consumer provider."""
    assert snmp_provider.is_consumer is True


def test_stop_consume_sets_flag_false(snmp_provider):
    """stop_consume() sets consume flag to False."""
    snmp_provider.consume = True
    snmp_provider._snmp_engine = None  # prevent cleanup error
    snmp_provider.stop_consume()
    assert snmp_provider.consume is False


def test_parse_trap_required_fields_always_present(snmp_provider):
    """_parse_trap always returns all fields required by _push_alert."""
    mock_engine = MagicMock()
    mock_engine.msgAndPduDsp.getTransportInfo.return_value = (
        None, ("1.2.3.4", 161)
    )

    result = snmp_provider._parse_trap([], mock_engine, MagicMock())

    required = [
        "id", "name", "source", "description",
        "severity", "status", "lastReceived",
        "trap_oid", "source_address",
    ]
    for field in required:
        assert field in result, f"Missing required _push_alert field: {field}"
