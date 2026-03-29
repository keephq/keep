"""
Comprehensive unit tests for the SNMP provider.

Tests cover:
  - Config validation (version, port, SNMPv3 username, poll_interval)
  - OID normalisation and prefix matching
  - Severity and status resolution (built-in OID map + user overrides)
  - Vendor detection
  - Webhook (push) alert parsing — single and batch
  - Alert field correctness (name, description, labels, source)
  - Lifecycle (dispose, _start_trap_listener guard)
  - Edge cases (missing fields, malformed JSON, empty varbinds, nested varbinds)
  - _get_alerts drains buffer and starts listener
  - Batch trap parsing
  - Standard RFC OIDs (coldStart, warmStart, linkDown, linkUp, authFailure, etc.)
  - Vendor prefix OIDs (Cisco, HP, Dell, Juniper, Huawei, VMware, Net-SNMP)
  - Topology returns list
  - Recovery detection heuristic
"""

import datetime
import json
import os
import threading
import unittest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import (
    SnmpProvider,
    SnmpProviderAuthConfig,
    _STANDARD_OID_MAP,
    _VENDOR_OID_PREFIXES,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(auth_overrides: dict | None = None) -> SnmpProvider:
    """Create a minimal SnmpProvider with default config."""
    base = {
        "host": os.environ["TEST_SNMP_HOST"] if "TEST_SNMP_HOST" in os.environ else "test-snmp-device",
        "port": 1620,
        "community_string": "public",
        "version": "2c",
        "oids_mapping": "{}",
        "poll_enabled": False,
        "poll_targets": "[]",
        "poll_interval": 60,
    }
    if auth_overrides:
        base.update(auth_overrides)
    ctx = MagicMock(spec=ContextManager)
    config = ProviderConfig(authentication=base)
    provider = SnmpProvider(context_manager=ctx, provider_id="test-snmp", config=config)
    provider.validate_config()
    return provider


def _alert_dto_from_payload(payload: dict) -> AlertDto:
    return SnmpProvider._format_alert(payload)


# ===========================================================================
# 1. Config validation
# ===========================================================================


class TestSnmpProviderAuthConfig(unittest.TestCase):
    def test_default_version_is_2c(self):
        provider = _make_provider()
        self.assertEqual(provider.authentication_config.version, "2c")

    def test_version_1_accepted(self):
        provider = _make_provider({"version": "1"})
        self.assertEqual(provider.authentication_config.version, "1")

    def test_version_3_accepted_with_username(self):
        provider = _make_provider({"version": "3", "username": "admin"})
        self.assertEqual(provider.authentication_config.version, "3")

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            _make_provider({"version": "5"})

    def test_v3_without_username_raises(self):
        with self.assertRaises(ValueError):
            _make_provider({"version": "3", "username": ""})

    def test_port_zero_raises(self):
        with self.assertRaises(ValueError):
            _make_provider({"port": 0})

    def test_port_too_high_raises(self):
        with self.assertRaises(ValueError):
            _make_provider({"port": 99999})

    def test_port_65535_accepted(self):
        provider = _make_provider({"port": 65535})
        self.assertEqual(provider.authentication_config.port, 65535)

    def test_poll_interval_zero_raises(self):
        with self.assertRaises(ValueError):
            _make_provider({"poll_interval": 0})

    def test_poll_interval_negative_raises(self):
        with self.assertRaises(ValueError):
            _make_provider({"poll_interval": -5})

    def test_default_community_is_public(self):
        provider = _make_provider()
        self.assertEqual(provider.authentication_config.community_string, "public")

    def test_custom_community_accepted(self):
        provider = _make_provider({"community_string": "private"})
        self.assertEqual(provider.authentication_config.community_string, "private")

    def test_invalid_oids_mapping_json_defaults_to_empty(self):
        provider = _make_provider({"oids_mapping": "NOT-JSON"})
        self.assertEqual(provider._oids_mapping, {})

    def test_invalid_poll_targets_json_defaults_to_empty(self):
        provider = _make_provider({"poll_targets": "NOT-JSON"})
        self.assertEqual(provider._poll_targets, [])

    def test_oids_mapping_not_object_defaults_to_empty(self):
        provider = _make_provider({"oids_mapping": "[1,2,3]"})
        self.assertEqual(provider._oids_mapping, {})

    def test_poll_targets_not_list_defaults_to_empty(self):
        provider = _make_provider({"poll_targets": '{"a": 1}'})
        self.assertEqual(provider._poll_targets, [])

    def test_valid_oids_mapping_parsed(self):
        mapping = json.dumps({"1.3.6.1.4.1.9": {"severity": "critical"}})
        provider = _make_provider({"oids_mapping": mapping})
        self.assertIn("1.3.6.1.4.1.9", provider._oids_mapping)

    def test_valid_poll_targets_parsed(self):
        targets = json.dumps([{"host": "10.0.0.1", "oids": ["1.3.6.1.2.1.1.1.0"]}])
        provider = _make_provider({"poll_targets": targets})
        self.assertEqual(len(provider._poll_targets), 1)


# ===========================================================================
# 2. OID normalisation
# ===========================================================================


class TestOidNormalisation(unittest.TestCase):
    def test_leading_dot_stripped(self):
        self.assertEqual(SnmpProvider._normalise_oid(".1.3.6.1.6.3.1.1.5.3"), "1.3.6.1.6.3.1.1.5.3")

    def test_no_leading_dot_unchanged(self):
        self.assertEqual(SnmpProvider._normalise_oid("1.3.6.1.6.3.1.1.5.3"), "1.3.6.1.6.3.1.1.5.3")

    def test_empty_string(self):
        self.assertEqual(SnmpProvider._normalise_oid(""), "")


# ===========================================================================
# 3. OID mapping resolution
# ===========================================================================


class TestResolveOidMapping(unittest.TestCase):
    def setUp(self):
        self.provider = _make_provider()

    def test_exact_match_in_standard_map(self):
        m = self.provider._resolve_oid_mapping("1.3.6.1.6.3.1.1.5.3")
        self.assertEqual(m.get("name"), "linkDown")

    def test_leading_dot_still_resolves(self):
        m = self.provider._resolve_oid_mapping(".1.3.6.1.6.3.1.1.5.3")
        self.assertEqual(m.get("name"), "linkDown")

    def test_no_match_returns_empty(self):
        m = self.provider._resolve_oid_mapping("9.9.9.9.9.9")
        self.assertEqual(m, {})

    def test_user_mapping_overrides_standard(self):
        mapping = json.dumps({"1.3.6.1.6.3.1.1.5.3": {"severity": "warning", "name": "Custom"}})
        provider = _make_provider({"oids_mapping": mapping})
        m = provider._resolve_oid_mapping("1.3.6.1.6.3.1.1.5.3")
        self.assertEqual(m.get("name"), "Custom")

    def test_user_prefix_match(self):
        mapping = json.dumps({"1.3.6.1.4.1.9": {"severity": "critical", "name": "Cisco"}})
        provider = _make_provider({"oids_mapping": mapping})
        m = provider._resolve_oid_mapping("1.3.6.1.4.1.9.1.100")
        self.assertEqual(m.get("name"), "Cisco")

    def test_longest_prefix_wins(self):
        mapping = json.dumps({
            "1.3.6.1.4.1.9": {"name": "Short"},
            "1.3.6.1.4.1.9.1": {"name": "Longer"},
        })
        provider = _make_provider({"oids_mapping": mapping})
        m = provider._resolve_oid_mapping("1.3.6.1.4.1.9.1.50")
        self.assertEqual(m.get("name"), "Longer")


# ===========================================================================
# 4. Severity and status helpers
# ===========================================================================


class TestSeverityAndStatus(unittest.TestCase):
    def test_critical_severity(self):
        s = SnmpProvider._severity_from_mapping({"severity": "critical"})
        self.assertEqual(s, AlertSeverity.CRITICAL)

    def test_high_severity(self):
        s = SnmpProvider._severity_from_mapping({"severity": "high"})
        self.assertEqual(s, AlertSeverity.HIGH)

    def test_warning_severity(self):
        s = SnmpProvider._severity_from_mapping({"severity": "warning"})
        self.assertEqual(s, AlertSeverity.WARNING)

    def test_warn_alias(self):
        s = SnmpProvider._severity_from_mapping({"severity": "warn"})
        self.assertEqual(s, AlertSeverity.WARNING)

    def test_info_severity(self):
        s = SnmpProvider._severity_from_mapping({"severity": "info"})
        self.assertEqual(s, AlertSeverity.INFO)

    def test_empty_mapping_defaults_to_info(self):
        s = SnmpProvider._severity_from_mapping({})
        self.assertEqual(s, AlertSeverity.INFO)

    def test_unknown_string_defaults_to_info(self):
        s = SnmpProvider._severity_from_mapping({"severity": "super-critical"})
        self.assertEqual(s, AlertSeverity.INFO)

    def test_alertseverity_passthrough(self):
        s = SnmpProvider._severity_from_mapping({"severity": AlertSeverity.CRITICAL})
        self.assertEqual(s, AlertSeverity.CRITICAL)

    def test_link_down_is_firing(self):
        st = SnmpProvider._status_from_mapping({"status": AlertStatus.FIRING}, "1.3.6.1.6.3.1.1.5.3")
        self.assertEqual(st, AlertStatus.FIRING)

    def test_link_up_name_is_resolved(self):
        st = SnmpProvider._status_from_mapping({"name": "linkUp"}, "1.3.6.1.6.3.1.1.5.4")
        self.assertEqual(st, AlertStatus.RESOLVED)

    def test_cold_start_name_is_resolved(self):
        st = SnmpProvider._status_from_mapping({"name": "coldStart"}, "1.3.6.1.6.3.1.1.5.1")
        self.assertEqual(st, AlertStatus.RESOLVED)

    def test_established_name_is_resolved(self):
        st = SnmpProvider._status_from_mapping({"name": "bgpEstablished"}, "")
        self.assertEqual(st, AlertStatus.RESOLVED)

    def test_no_status_field_defaults_to_firing(self):
        st = SnmpProvider._status_from_mapping({}, "9.9.9.9")
        self.assertEqual(st, AlertStatus.FIRING)

    def test_alertstatus_passthrough(self):
        st = SnmpProvider._status_from_mapping({"status": AlertStatus.RESOLVED}, "")
        self.assertEqual(st, AlertStatus.RESOLVED)


# ===========================================================================
# 5. Vendor detection
# ===========================================================================


class TestVendorDetection(unittest.TestCase):
    def test_cisco_prefix(self):
        self.assertEqual(SnmpProvider._vendor_from_oid("1.3.6.1.4.1.9.1.100"), "Cisco")

    def test_hp_prefix(self):
        self.assertEqual(SnmpProvider._vendor_from_oid("1.3.6.1.4.1.11.2.14"), "HP")

    def test_dell_prefix(self):
        self.assertEqual(SnmpProvider._vendor_from_oid("1.3.6.1.4.1.674.10892.5"), "Dell")

    def test_juniper_prefix(self):
        self.assertEqual(SnmpProvider._vendor_from_oid("1.3.6.1.4.1.2636.3.1"), "Juniper")

    def test_huawei_prefix(self):
        self.assertEqual(SnmpProvider._vendor_from_oid("1.3.6.1.4.1.2011.5.25"), "Huawei")

    def test_vmware_prefix(self):
        self.assertEqual(SnmpProvider._vendor_from_oid("1.3.6.1.4.1.6876.4"), "VMware")

    def test_netsnmp_prefix(self):
        self.assertEqual(SnmpProvider._vendor_from_oid("1.3.6.1.4.1.8072.1.3"), "Net-SNMP")

    def test_leading_dot_ignored(self):
        self.assertEqual(SnmpProvider._vendor_from_oid(".1.3.6.1.4.1.9.9.1"), "Cisco")

    def test_unknown_vendor(self):
        self.assertEqual(SnmpProvider._vendor_from_oid("9.9.9.9"), "Unknown")

    def test_standard_oid_is_unknown_vendor(self):
        self.assertEqual(SnmpProvider._vendor_from_oid("1.3.6.1.6.3.1.1.5.3"), "Unknown")


# ===========================================================================
# 6. Standard OID map coverage
# ===========================================================================


class TestStandardOidMap(unittest.TestCase):
    def test_cold_start_info(self):
        m = _STANDARD_OID_MAP["1.3.6.1.6.3.1.1.5.1"]
        self.assertEqual(m["severity"], AlertSeverity.INFO)

    def test_warm_start_resolved(self):
        m = _STANDARD_OID_MAP["1.3.6.1.6.3.1.1.5.2"]
        self.assertEqual(m["status"], AlertStatus.RESOLVED)

    def test_link_down_critical_firing(self):
        m = _STANDARD_OID_MAP["1.3.6.1.6.3.1.1.5.3"]
        self.assertEqual(m["severity"], AlertSeverity.CRITICAL)
        self.assertEqual(m["status"], AlertStatus.FIRING)

    def test_link_up_resolved(self):
        m = _STANDARD_OID_MAP["1.3.6.1.6.3.1.1.5.4"]
        self.assertEqual(m["status"], AlertStatus.RESOLVED)

    def test_auth_failure_high(self):
        m = _STANDARD_OID_MAP["1.3.6.1.6.3.1.1.5.5"]
        self.assertEqual(m["severity"], AlertSeverity.HIGH)

    def test_bgp_established_resolved(self):
        m = _STANDARD_OID_MAP["1.3.6.1.2.1.15.7"]
        self.assertEqual(m["status"], AlertStatus.RESOLVED)

    def test_bgp_backward_transition_firing(self):
        m = _STANDARD_OID_MAP["1.3.6.1.2.1.15.8"]
        self.assertEqual(m["status"], AlertStatus.FIRING)

    def test_ups_battery_low_critical(self):
        m = _STANDARD_OID_MAP["1.3.6.1.2.1.33.2.0.2"]
        self.assertEqual(m["severity"], AlertSeverity.CRITICAL)

    def test_ups_on_battery_warning(self):
        m = _STANDARD_OID_MAP["1.3.6.1.2.1.33.2.0.3"]
        self.assertEqual(m["severity"], AlertSeverity.WARNING)

    def test_all_standard_oids_have_severity(self):
        for oid, mapping in _STANDARD_OID_MAP.items():
            self.assertIn("severity", mapping, f"Missing severity for OID {oid}")

    def test_all_standard_oids_have_name(self):
        for oid, mapping in _STANDARD_OID_MAP.items():
            self.assertIn("name", mapping, f"Missing name for OID {oid}")


# ===========================================================================
# 7. Webhook (push) alert parsing — single
# ===========================================================================


class TestFormatAlertSingle(unittest.TestCase):
    def _basic_payload(self, **kwargs) -> dict:
        base = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source": "192.168.1.1",
            "version": "2c",
            "community": "public",
            "varbinds": [{"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux device"}],
        }
        base.update(kwargs)
        return base

    def test_returns_alert_dto(self):
        alert = _alert_dto_from_payload(self._basic_payload())
        self.assertIsInstance(alert, AlertDto)

    def test_name_from_standard_map(self):
        alert = _alert_dto_from_payload(self._basic_payload(trap_oid="1.3.6.1.6.3.1.1.5.3"))
        self.assertEqual(alert.name, "linkDown")

    def test_severity_link_down_is_critical(self):
        alert = _alert_dto_from_payload(self._basic_payload(trap_oid="1.3.6.1.6.3.1.1.5.3"))
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_status_link_down_is_firing(self):
        alert = _alert_dto_from_payload(self._basic_payload(trap_oid="1.3.6.1.6.3.1.1.5.3"))
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_link_up_is_resolved(self):
        alert = _alert_dto_from_payload(self._basic_payload(trap_oid="1.3.6.1.6.3.1.1.5.4"))
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_cold_start_is_info_resolved(self):
        alert = _alert_dto_from_payload(self._basic_payload(trap_oid="1.3.6.1.6.3.1.1.5.1"))
        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_auth_failure_is_high(self):
        alert = _alert_dto_from_payload(self._basic_payload(trap_oid="1.3.6.1.6.3.1.1.5.5"))
        self.assertEqual(alert.severity, AlertSeverity.HIGH)

    def test_source_address_set(self):
        alert = _alert_dto_from_payload(self._basic_payload(source="10.0.0.5"))
        self.assertEqual(alert.source_address, "10.0.0.5")

    def test_snmp_version_in_alert(self):
        alert = _alert_dto_from_payload(self._basic_payload(version="3"))
        self.assertEqual(alert.snmp_version, "3")

    def test_vendor_cisco(self):
        alert = _alert_dto_from_payload(self._basic_payload(trap_oid="1.3.6.1.4.1.9.1.100"))
        self.assertEqual(alert.vendor, "Cisco")

    def test_vendor_unknown_for_standard(self):
        alert = _alert_dto_from_payload(self._basic_payload(trap_oid="1.3.6.1.6.3.1.1.5.3"))
        self.assertEqual(alert.vendor, "Unknown")

    def test_varbinds_in_description(self):
        alert = _alert_dto_from_payload(self._basic_payload())
        self.assertIn("1.3.6.1.2.1.1.1.0", alert.description)

    def test_source_in_labels(self):
        alert = _alert_dto_from_payload(self._basic_payload(source="10.1.2.3"))
        self.assertEqual(alert.labels.get("source_address"), "10.1.2.3")

    def test_trap_oid_in_labels(self):
        alert = _alert_dto_from_payload(self._basic_payload())
        self.assertIn("trap_oid", alert.labels)

    def test_snmp_source_in_source_list(self):
        alert = _alert_dto_from_payload(self._basic_payload())
        self.assertIn("snmp", alert.source)

    def test_oid_alias_field(self):
        payload = {"oid": "1.3.6.1.6.3.1.1.5.3", "source": "10.0.0.1", "varbinds": []}
        alert = _alert_dto_from_payload(payload)
        self.assertEqual(alert.name, "linkDown")

    def test_snmptrapoid_field(self):
        payload = {"snmpTrapOID": "1.3.6.1.6.3.1.1.5.3", "source": "10.0.0.1", "varbinds": []}
        alert = _alert_dto_from_payload(payload)
        self.assertEqual(alert.name, "linkDown")

    def test_agentaddress_field(self):
        payload = {"trap_oid": "1.3.6.1.6.3.1.1.5.3", "agentAddress": "172.16.0.1", "varbinds": []}
        alert = _alert_dto_from_payload(payload)
        self.assertEqual(alert.source_address, "172.16.0.1")

    def test_empty_varbinds(self):
        alert = _alert_dto_from_payload(self._basic_payload(varbinds=[]))
        self.assertIsInstance(alert, AlertDto)

    def test_leading_dot_oid_resolves(self):
        payload = self._basic_payload(trap_oid=".1.3.6.1.6.3.1.1.5.3")
        alert = _alert_dto_from_payload(payload)
        self.assertEqual(alert.name, "linkDown")

    def test_unknown_oid_fallback_name(self):
        alert = _alert_dto_from_payload(self._basic_payload(trap_oid="9.9.9.9.9"))
        self.assertIn("9.9.9.9.9", alert.name)

    def test_custom_name_field(self):
        alert = _alert_dto_from_payload(self._basic_payload(name="MyCustomAlert"))
        self.assertEqual(alert.name, "MyCustomAlert")

    def test_tuple_varbind_accepted(self):
        payload = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source": "10.0.0.1",
            "varbinds": [["1.3.6.1.2.1.1.1.0", "Linux device"]],
        }
        alert = _alert_dto_from_payload(payload)
        self.assertIn("1.3.6.1.2.1.1.1.0", alert.description)

    def test_community_in_labels(self):
        alert = _alert_dto_from_payload(self._basic_payload(community="private"))
        self.assertEqual(alert.labels.get("community"), "private")

    def test_no_community_not_in_labels(self):
        payload = {"trap_oid": "1.3.6.1.6.3.1.1.5.3", "source": "10.0.0.1", "varbinds": []}
        alert = _alert_dto_from_payload(payload)
        self.assertNotIn("community", alert.labels)

    def test_id_is_uuid(self):
        import uuid
        alert = _alert_dto_from_payload(self._basic_payload())
        uuid.UUID(alert.id)  # should not raise

    def test_last_received_is_set(self):
        alert = _alert_dto_from_payload(self._basic_payload())
        self.assertIsNotNone(alert.lastReceived)


# ===========================================================================
# 8. Webhook (push) alert parsing — batch
# ===========================================================================


class TestFormatAlertBatch(unittest.TestCase):
    def _batch_payload(self) -> dict:
        return {
            "traps": [
                {"trap_oid": "1.3.6.1.6.3.1.1.5.3", "source": "10.0.0.1", "varbinds": []},
                {"trap_oid": "1.3.6.1.6.3.1.1.5.4", "source": "10.0.0.2", "varbinds": []},
            ]
        }

    def test_batch_returns_list(self):
        result = SnmpProvider._format_alert(self._batch_payload())
        self.assertIsInstance(result, list)

    def test_batch_count(self):
        result = SnmpProvider._format_alert(self._batch_payload())
        self.assertEqual(len(result), 2)

    def test_batch_items_are_alertdtos(self):
        result = SnmpProvider._format_alert(self._batch_payload())
        for item in result:
            self.assertIsInstance(item, AlertDto)

    def test_batch_severities_correct(self):
        result = SnmpProvider._format_alert(self._batch_payload())
        self.assertEqual(result[0].severity, AlertSeverity.CRITICAL)  # linkDown
        self.assertEqual(result[1].status, AlertStatus.RESOLVED)  # linkUp

    def test_empty_traps_list_falls_back(self):
        # With empty traps list, falls back to parsing the envelope
        payload = {"traps": [], "trap_oid": "1.3.6.1.6.3.1.1.5.3", "source": "10.0.0.1", "varbinds": []}
        result = SnmpProvider._format_alert(payload)
        # Either list or single is fine
        if isinstance(result, list):
            self.assertEqual(len(result), 1)
        else:
            self.assertIsInstance(result, AlertDto)

    def test_single_dict_returns_alert_dto(self):
        payload = {"trap_oid": "1.3.6.1.6.3.1.1.5.3", "source": "10.0.0.1", "varbinds": []}
        result = SnmpProvider._format_alert(payload)
        self.assertIsInstance(result, AlertDto)


# ===========================================================================
# 9. _get_alerts drains buffer
# ===========================================================================


class TestGetAlerts(unittest.TestCase):
    def test_get_alerts_returns_list(self):
        provider = _make_provider()
        with patch.object(provider, "_start_trap_listener"):
            result = provider._get_alerts()
        self.assertIsInstance(result, list)

    def test_get_alerts_drains_buffer(self):
        provider = _make_provider()
        fake_alert = MagicMock(spec=AlertDto)
        with provider._alerts_lock:
            provider._alerts.append(fake_alert)
        with patch.object(provider, "_start_trap_listener"):
            result = provider._get_alerts()
        self.assertIn(fake_alert, result)
        self.assertEqual(len(provider._alerts), 0)

    def test_get_alerts_calls_start_listener(self):
        provider = _make_provider()
        with patch.object(provider, "_start_trap_listener") as mock_start:
            provider._get_alerts()
        mock_start.assert_called_once()


# ===========================================================================
# 10. Lifecycle — dispose
# ===========================================================================


class TestDispose(unittest.TestCase):
    def test_dispose_sets_stop_event(self):
        provider = _make_provider()
        provider.dispose()
        self.assertTrue(provider._stop_event.is_set())

    def test_dispose_with_no_thread_does_not_raise(self):
        provider = _make_provider()
        provider._listener_thread = None
        try:
            provider.dispose()
        except Exception as exc:
            self.fail(f"dispose() raised {exc}")

    def test_dispose_joins_running_thread(self):
        provider = _make_provider()
        finished = threading.Event()

        def slow_listener():
            provider._stop_event.wait(timeout=10)
            finished.set()

        t = threading.Thread(target=slow_listener, daemon=True)
        t.start()
        provider._listener_thread = t
        provider.dispose()
        self.assertTrue(finished.is_set())
        self.assertIsNone(provider._listener_thread)


# ===========================================================================
# 11. Start listener guard
# ===========================================================================


class TestStartListenerGuard(unittest.TestCase):
    def test_start_listener_no_op_when_pysnmp_unavailable(self):
        provider = _make_provider()
        with patch("keep.providers.snmp_provider.snmp_provider.PYSNMP_AVAILABLE", False):
            provider._start_trap_listener()
        self.assertIsNone(provider._listener_thread)

    def test_start_listener_no_op_when_already_running(self):
        provider = _make_provider()
        fake_thread = MagicMock(spec=threading.Thread)
        fake_thread.is_alive.return_value = True
        provider._listener_thread = fake_thread
        with patch("keep.providers.snmp_provider.snmp_provider.PYSNMP_AVAILABLE", True):
            provider._start_trap_listener()
        # Should not create a new thread
        self.assertEqual(provider._listener_thread, fake_thread)


# ===========================================================================
# 12. Topology
# ===========================================================================


class TestTopology(unittest.TestCase):
    def test_topology_returns_list(self):
        provider = _make_provider()
        result = provider.get_topology()
        self.assertIsInstance(result, list)

    def test_topology_empty_without_poll_targets(self):
        provider = _make_provider()
        result = provider.get_topology()
        self.assertEqual(result, [])

    def test_topology_with_poll_targets(self):
        targets = json.dumps([{"host": "10.0.0.1", "oids": []}])
        provider = _make_provider({"poll_targets": targets})
        with patch("keep.providers.snmp_provider.snmp_provider.PYSNMP_AVAILABLE", True):
            result = provider.get_topology()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["host"], "10.0.0.1")


# ===========================================================================
# 13. Build alert from trap (internal)
# ===========================================================================


class TestBuildAlertFromTrap(unittest.TestCase):
    def setUp(self):
        self.provider = _make_provider()

    def test_link_down_builds_correctly(self):
        alert = self.provider._build_alert_from_trap(
            trap_oid="1.3.6.1.6.3.1.1.5.3",
            source_address="192.168.1.10",
            varbinds=[("1.3.6.1.2.1.2.2.1.1.1", "1")],
        )
        self.assertEqual(alert.name, "linkDown")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.source_address, "192.168.1.10")

    def test_varbinds_appear_in_description(self):
        alert = self.provider._build_alert_from_trap(
            trap_oid="1.3.6.1.6.3.1.1.5.3",
            source_address="10.0.0.1",
            varbinds=[("1.3.6.1.2.1.1.1.0", "My Device")],
        )
        self.assertIn("My Device", alert.description)

    def test_snmp_version_v1(self):
        alert = self.provider._build_alert_from_trap(
            trap_oid="1.3.6.1.6.3.1.1.5.1",
            source_address="10.0.0.1",
            varbinds=[],
            snmp_version="1",
        )
        self.assertEqual(alert.snmp_version, "1")

    def test_community_in_labels(self):
        alert = self.provider._build_alert_from_trap(
            trap_oid="1.3.6.1.6.3.1.1.5.3",
            source_address="10.0.0.1",
            varbinds=[],
            community="private",
        )
        self.assertEqual(alert.labels.get("community"), "private")

    def test_no_community_not_in_labels(self):
        alert = self.provider._build_alert_from_trap(
            trap_oid="1.3.6.1.6.3.1.1.5.3",
            source_address="10.0.0.1",
            varbinds=[],
            community="",
        )
        self.assertNotIn("community", alert.labels)

    def test_many_varbinds_capped_at_10_in_description(self):
        varbinds = [(f"1.3.6.1.2.1.{i}.0", f"val{i}") for i in range(20)]
        alert = self.provider._build_alert_from_trap(
            trap_oid="1.3.6.1.6.3.1.1.5.3",
            source_address="10.0.0.1",
            varbinds=varbinds,
        )
        # Only first 10 varbinds in description
        self.assertIn("val9", alert.description)
        self.assertNotIn("val10", alert.description)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main()
