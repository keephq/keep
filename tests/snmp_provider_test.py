"""
Unit tests for the Keep SNMP provider.

Tests focus on the pure-Python logic (alert formatting, fingerprinting,
severity/status mapping, config validation, simulate_alert) without requiring
a live SNMP agent or network socket.
"""
import datetime
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def provider():
    """Create a SnmpProvider with minimal configuration."""
    config = ProviderConfig(
        authentication={
            "listen_port": 11621,
            "community_string": "public",
            "snmp_version": "2c",
        }
    )
    ctx = MagicMock()
    ctx.tenant_id = "test-tenant"
    p = SnmpProvider(ctx, "snmp-test", config)
    return p


@pytest.fixture
def v3_provider():
    """Create a SnmpProvider configured for SNMPv3."""
    config = ProviderConfig(
        authentication={
            "snmp_version": "3",
            "v3_username": "keepuser",
            "v3_auth_protocol": "SHA",
            "v3_auth_key": "authpassword1",
            "v3_priv_protocol": "AES",
            "v3_priv_key": "privpassword1",
        }
    )
    ctx = MagicMock()
    ctx.tenant_id = "test-tenant"
    return SnmpProvider(ctx, "snmp-v3-test", config)


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults_applied(self, provider):
        cfg = provider.authentication_config
        assert cfg.listen_port == 11621
        assert cfg.listen_address == "0.0.0.0"
        assert cfg.community_string == "public"
        assert cfg.snmp_version == "2c"
        assert cfg.target_host == ""
        assert cfg.target_port == 161

    def test_v3_config_stored(self, v3_provider):
        cfg = v3_provider.authentication_config
        assert cfg.snmp_version == "3"
        assert cfg.v3_username == "keepuser"
        assert cfg.v3_auth_key == "authpassword1"
        assert cfg.v3_priv_key == "privpassword1"

    def test_validate_scopes_success(self, provider):
        """validate_scopes should return True if port is bindable."""
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value = mock_sock
            result = provider.validate_scopes()
        assert result["receive_traps"] is True

    def test_validate_scopes_failure(self, provider):
        """validate_scopes returns error string when port bind fails."""
        import socket

        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.bind.side_effect = OSError("Address already in use")
            mock_sock_cls.return_value = mock_sock
            result = provider.validate_scopes()
        assert result["receive_traps"] == "Address already in use"


# ---------------------------------------------------------------------------
# _format_alert tests
# ---------------------------------------------------------------------------


class TestFormatAlert:
    def _event(self, trap_name="linkDown", host="192.168.1.1", varbinds=None):
        return {
            "host": host,
            "trap_oid": SnmpProvider._STANDARD_TRAP_OIDS.get(
                trap_name, "1.3.6.1.6.3.1.1.5.3"
            ),
            "trap_name": trap_name,
            "varbinds": varbinds or {},
            "snmp_version": "v2c",
        }

    def test_returns_list_of_one(self):
        alerts = SnmpProvider._format_alert(self._event())
        assert isinstance(alerts, list)
        assert len(alerts) == 1

    def test_linkdown_severity_and_status(self):
        alert = SnmpProvider._format_alert(self._event("linkDown"))[0]
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.FIRING

    def test_linkup_severity_and_status(self):
        alert = SnmpProvider._format_alert(self._event("linkUp"))[0]
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.RESOLVED

    def test_coldstart_is_warning_firing(self):
        alert = SnmpProvider._format_alert(self._event("coldStart"))[0]
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING

    def test_authentication_failure_severity(self):
        alert = SnmpProvider._format_alert(self._event("authenticationFailure"))[0]
        assert alert.severity == AlertSeverity.WARNING

    def test_unknown_trap_defaults_to_warning_firing(self):
        event = {
            "host": "1.2.3.4",
            "trap_oid": "1.3.6.1.4.1.99999.1.1",
            "trap_name": "1.3.6.1.4.1.99999.1.1",
            "varbinds": {},
            "snmp_version": "v2c",
        }
        alert = SnmpProvider._format_alert(event)[0]
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING

    def test_cisco_enterprise_oid_maps_to_warning(self):
        event = {
            "host": "10.0.0.1",
            "trap_oid": "1.3.6.1.4.1.9.9.43.2.0.1",
            "trap_name": "1.3.6.1.4.1.9.9.43.2.0.1",
            "varbinds": {},
            "snmp_version": "v2c",
        }
        alert = SnmpProvider._format_alert(event)[0]
        assert alert.severity == AlertSeverity.WARNING

    def test_source_always_snmp(self):
        alert = SnmpProvider._format_alert(self._event())[0]
        assert "snmp" in alert.source

    def test_host_in_labels(self):
        alert = SnmpProvider._format_alert(self._event(host="10.1.2.3"))[0]
        assert alert.labels["host"] == "10.1.2.3"

    def test_varbinds_included_in_labels(self):
        event = self._event(varbinds={"1.3.6.1.2.1.2.2.1.2.2": "eth0"})
        alert = SnmpProvider._format_alert(event)[0]
        assert alert.labels.get("1.3.6.1.2.1.2.2.1.2.2") == "eth0"

    def test_varbind_string_in_message(self):
        event = self._event(varbinds={"oid.1": "val1"})
        alert = SnmpProvider._format_alert(event)[0]
        assert alert.message is not None
        assert "val1" in alert.message

    def test_empty_varbinds_message_is_none(self):
        alert = SnmpProvider._format_alert(self._event())[0]
        assert alert.message is None

    def test_last_received_is_set(self):
        alert = SnmpProvider._format_alert(self._event())[0]
        assert alert.lastReceived is not None

    def test_custom_timestamp_respected(self):
        ts = "2025-01-01T00:00:00+00:00"
        event = dict(self._event())
        event["timestamp"] = ts
        alert = SnmpProvider._format_alert(event)[0]
        assert alert.lastReceived == ts


# ---------------------------------------------------------------------------
# Fingerprint tests
# ---------------------------------------------------------------------------


class TestFingerprint:
    def test_same_inputs_produce_same_fingerprint(self):
        f1 = SnmpProvider._compute_fingerprint_static("1.2.3.4", "1.3.6.1.6.3.1.1.5.3")
        f2 = SnmpProvider._compute_fingerprint_static("1.2.3.4", "1.3.6.1.6.3.1.1.5.3")
        assert f1 == f2

    def test_different_hosts_different_fingerprints(self):
        f1 = SnmpProvider._compute_fingerprint_static("1.2.3.4", "oid")
        f2 = SnmpProvider._compute_fingerprint_static("5.6.7.8", "oid")
        assert f1 != f2

    def test_different_oids_different_fingerprints(self):
        f1 = SnmpProvider._compute_fingerprint_static("host", "oid.1")
        f2 = SnmpProvider._compute_fingerprint_static("host", "oid.2")
        assert f1 != f2

    def test_fingerprint_is_hex_string(self):
        fp = SnmpProvider._compute_fingerprint_static("host", "oid")
        int(fp, 16)  # should not raise


# ---------------------------------------------------------------------------
# OID resolution tests
# ---------------------------------------------------------------------------


class TestOidResolution:
    def test_known_oid_resolves_to_name(self):
        name = SnmpProvider._resolve_oid_name("1.3.6.1.6.3.1.1.5.3")
        assert name == "linkDown"

    def test_linkup_oid(self):
        assert SnmpProvider._resolve_oid_name("1.3.6.1.6.3.1.1.5.4") == "linkUp"

    def test_unknown_oid_returns_itself(self):
        raw = "1.3.6.1.4.1.99999.1.2.3"
        assert SnmpProvider._resolve_oid_name(raw) == raw


# ---------------------------------------------------------------------------
# simulate_alert tests
# ---------------------------------------------------------------------------


class TestSimulateAlert:
    def test_returns_dict(self, provider):
        result = SnmpProvider.simulate_alert(alert_type="linkDown")
        assert isinstance(result, dict)

    def test_required_fields_present(self):
        result = SnmpProvider.simulate_alert(alert_type="coldStart")
        assert "host" in result
        assert "trap_name" in result
        assert "trap_oid" in result

    def test_all_alert_types_valid(self):
        for atype in ["linkDown", "linkUp", "coldStart",
                      "authenticationFailure", "enterpriseTrap"]:
            result = SnmpProvider.simulate_alert(alert_type=atype)
            assert result["trap_name"] is not None

    def test_timestamp_is_set(self):
        result = SnmpProvider.simulate_alert(alert_type="linkDown")
        assert "timestamp" in result

    def test_no_arg_uses_random_type(self):
        result = SnmpProvider.simulate_alert()
        assert "trap_name" in result


# ---------------------------------------------------------------------------
# dispose / stop event tests
# ---------------------------------------------------------------------------


class TestDispose:
    def test_dispose_without_thread_does_not_raise(self, provider):
        provider.dispose()  # should not raise

    def test_dispose_sets_stop_event(self, provider):
        provider.dispose()
        assert provider._stop_event.is_set()
