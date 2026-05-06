"""Unit tests for the SNMP trap listener provider.

These tests intentionally avoid spinning up a real SNMP dispatcher so they
remain fast and hermetic. They cover:

* config validation (port range, version whitelist)
* OID -> severity heuristic
* trap-to-AlertDto mapping
* validate_scopes binding behavior
* stop_consume flips the consume flag

The actual dispatcher loop is exercised via integration in production; here
we mock the bind-to-port path so tests do not require root or SNMP libraries
to be running on the host.
"""

import socket

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import (
    SnmpProvider,
    SnmpProviderAuthConfig,
)


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")


def _make_provider(context_manager, **overrides):
    auth = {
        "listen_host": "127.0.0.1",
        "listen_port": 11620,
        "community_string": "public",
        "snmp_version": "v2c",
    }
    auth.update(overrides)
    return SnmpProvider(
        context_manager=context_manager,
        provider_id="test_snmp_provider",
        config=ProviderConfig(description="Test SNMP", authentication=auth),
    )


class TestSnmpProviderConfig:
    def test_defaults(self):
        cfg = SnmpProviderAuthConfig()
        assert cfg.listen_host == "0.0.0.0"
        assert cfg.listen_port == 162
        assert cfg.community_string == "public"
        assert cfg.snmp_version == "v2c"

    def test_validate_config_accepts_v1_and_v2c(self, context_manager):
        for v in ("v1", "v2c", "V1", "V2C"):
            provider = _make_provider(context_manager, snmp_version=v)
            # Should not raise.
            provider.validate_config()

    def test_validate_config_rejects_v3(self, context_manager):
        provider = _make_provider(context_manager, snmp_version="v3")
        with pytest.raises(ValueError, match="Unsupported SNMP version"):
            provider.validate_config()

    def test_validate_config_rejects_bad_port(self, context_manager):
        provider = _make_provider(context_manager, listen_port=70000)
        with pytest.raises(ValueError, match="listen_port"):
            provider.validate_config()


class TestSeverityHeuristic:
    @pytest.mark.parametrize(
        "trap_oid,var_binds,expected",
        [
            ("1.3.6.1.4.1.9.9.41.1.2.3.CRITICAL", {}, "critical"),
            ("1.3.6.1.4.1.x", {"oid": "warning state"}, "warning"),
            ("1.3.6.1.4.1.x", {"oid": "ERROR thrown"}, "high"),
            ("1.3.6.1.4.1.x", {"oid": "informational"}, "info"),
            ("1.3.6.1.4.1.x", {"oid": "debug spam"}, "low"),
            ("1.3.6.1.4.1.x", {"oid": "nothing-special"}, "info"),
        ],
    )
    def test_severity_mapping(self, context_manager, trap_oid, var_binds, expected):
        provider = _make_provider(context_manager)
        provider.validate_config()
        assert provider._severity_from_trap(trap_oid, var_binds) == expected


class TestTrapToAlert:
    def test_basic_mapping(self, context_manager):
        provider = _make_provider(context_manager)
        provider.validate_config()

        alert = provider._trap_to_alert(
            trap_oid="1.3.6.1.6.3.1.1.5.3",
            var_binds={
                "1.3.6.1.2.1.1.3.0": "12345",
                "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.3",
                "1.3.6.1.2.1.2.2.1.1.2": "ifIndex=2",
            },
            source_address="10.0.0.5:51234",
        )

        assert alert["name"] == "1.3.6.1.6.3.1.1.5.3"
        assert alert["status"] == "firing"
        assert alert["source"] == ["snmp"]
        assert alert["severity"] == "info"  # nothing in var_binds maps elsewhere
        assert alert["fingerprint"] == "1.3.6.1.6.3.1.1.5.3"
        assert alert["labels"]["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"
        assert alert["labels"]["snmp_version"] == "v2c"
        assert alert["labels"]["source_address"] == "10.0.0.5:51234"
        # Each var bind is mirrored as a label so it can be filtered on.
        assert alert["labels"]["1.3.6.1.2.1.2.2.1.1.2"] == "ifIndex=2"
        # Description preserves all var binds in human-readable form.
        assert "1.3.6.1.2.1.1.3.0 = 12345" in alert["description"]

    def test_empty_var_binds_still_produces_alert(self, context_manager):
        provider = _make_provider(context_manager)
        provider.validate_config()

        alert = provider._trap_to_alert(trap_oid="1.2.3", var_binds={})
        assert alert["description"] == "SNMP trap received"
        assert alert["name"] == "1.2.3"


class TestValidateScopes:
    def test_validate_scopes_success(self, context_manager):
        # Pick an ephemeral high port that's unlikely to be taken.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        provider = _make_provider(context_manager, listen_port=port)
        provider.validate_config()
        assert provider.validate_scopes() == {"receive_traps": True}

    def test_validate_scopes_failure(self, context_manager):
        # Hold a socket on a port and try to bind a second time.
        held = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        held.bind(("127.0.0.1", 0))
        port = held.getsockname()[1]
        try:
            provider = _make_provider(context_manager, listen_port=port)
            provider.validate_config()
            result = provider.validate_scopes()
            # We get a string error back for a busy port, not a True.
            assert result["receive_traps"] is not True
            assert isinstance(result["receive_traps"], str)
        finally:
            held.close()


class TestLifecycle:
    def test_status_before_start(self, context_manager):
        provider = _make_provider(context_manager)
        provider.validate_config()
        assert provider.status() == {"status": "not-initialized", "error": ""}

    def test_stop_consume_flips_flag(self, context_manager):
        provider = _make_provider(context_manager)
        provider.validate_config()
        provider.consume = True
        provider.stop_consume()
        assert provider.consume is False
