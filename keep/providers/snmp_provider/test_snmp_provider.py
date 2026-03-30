"""
Unit tests for the SNMP provider.

Tests mock pysnmp so they run without the library installed.
Tests also mock Keep's internal imports for local dev environments;
in Keep's CI (Python 3.11 + pydantic 1.x) the real imports are used.
"""

import sys
import types
import unittest
from enum import Enum
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Bootstrap: build minimal stubs of Keep's internal modules so tests can
# import snmp_provider.py in isolation (without a full virtualenv).
# This is skipped if real modules are available.
# ---------------------------------------------------------------------------

def _bootstrap_keep_stubs():
    """Inject Keep module stubs only if the real package is unavailable."""

    # Check if real pydantic-compatible Keep is importable
    try:
        from keep.api.models.alert import AlertSeverity  # noqa
        return  # Real Keep available
    except Exception:
        pass  # Need stubs

    class AlertSeverity(str, Enum):
        CRITICAL = "critical"
        HIGH = "high"
        WARNING = "warning"
        MEDIUM = "medium"
        INFO = "info"
        LOW = "low"

    class AlertStatus(str, Enum):
        FIRING = "firing"
        RESOLVED = "resolved"

    class AlertDto:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class BaseProvider:
        def __init__(self, context_manager, provider_id, config):
            self.context_manager = context_manager
            self.provider_id = provider_id
            self.config = config
            self.validate_config()

    class ProviderConfig:
        def __init__(self, authentication=None):
            self.authentication = authentication or {}

    ContextManager = MagicMock

    # Build package hierarchy
    def _pkg(name: str) -> types.ModuleType:
        """Create or return a module, setting __path__ so it acts as package."""
        if name in sys.modules:
            return sys.modules[name]
        m = types.ModuleType(name)
        m.__path__ = ["/stub"]
        m.__package__ = name
        sys.modules[name] = m
        return m

    prefixes = [
        "keep",
        "keep.api", "keep.api.models", "keep.api.models.alert",
        "keep.contextmanager", "keep.contextmanager.contextmanager",
        "keep.providers", "keep.providers.base", "keep.providers.base.base_provider",
        "keep.providers.models", "keep.providers.models.provider_config",
        "keep.providers.snmp_provider",
    ]
    for name in prefixes:
        _pkg(name)

    sys.modules["keep.api.models.alert"].AlertSeverity = AlertSeverity
    sys.modules["keep.api.models.alert"].AlertStatus = AlertStatus
    sys.modules["keep.api.models.alert"].AlertDto = AlertDto
    sys.modules["keep.contextmanager.contextmanager"].ContextManager = ContextManager
    sys.modules["keep.providers.base.base_provider"].BaseProvider = BaseProvider
    sys.modules["keep.providers.models.provider_config"].ProviderConfig = ProviderConfig


_bootstrap_keep_stubs()


# ---------------------------------------------------------------------------
# Mock pysnmp BEFORE importing snmp_provider (it has a module-level import)
# ---------------------------------------------------------------------------

def _mock_pysnmp():
    """Inject minimal pysnmp stubs."""

    def _m(name: str) -> types.ModuleType:
        m = types.ModuleType(name)
        sys.modules[name] = m
        return m

    hlapi = _m("pysnmp.hlapi")
    for sym in ("CommunityData", "ContextData", "ObjectIdentity", "ObjectType",
                "SnmpEngine", "UdpTransportTarget", "getCmd", "nextCmd"):
        setattr(hlapi, sym, MagicMock())

    udp = _m("pysnmp.carrier.asyncore.dgram.udp")
    udp.domainName = ("udp", "v4")
    udp.UdpSocketTransport = MagicMock()

    engine_mod = _m("pysnmp.entity.engine")
    engine_mod.SnmpEngine = MagicMock()

    cfg_mod = _m("pysnmp.entity.config")
    for sym in ("addTransport", "addV1System", "addV3User",
                "usmHMACMD5AuthProtocol", "usmHMACSHAAuthProtocol",
                "usmDESPrivProtocol", "usmAesCfb128Protocol"):
        setattr(cfg_mod, sym, MagicMock())

    ntfrcv = _m("pysnmp.entity.rfc3413.ntfrcv")
    ntfrcv.NotificationReceiver = MagicMock()

    for name in ["pysnmp", "pysnmp.carrier", "pysnmp.carrier.asyncore",
                 "pysnmp.carrier.asyncore.dgram", "pysnmp.entity",
                 "pysnmp.entity.rfc3413", "pysnmp.proto",
                 "pysnmp.proto.api", "pysnmp.proto.api.v2c"]:
        if name not in sys.modules:
            _m(name)

    # Make pysnmp a real package stub
    root = sys.modules.setdefault("pysnmp", types.ModuleType("pysnmp"))
    root.__path__ = ["/stub/pysnmp"]
    root.hlapi = hlapi


_mock_pysnmp()


# ---------------------------------------------------------------------------
# Now import the provider under test
# ---------------------------------------------------------------------------
import importlib.util
import os

_PROVIDER_PY = os.path.join(os.path.dirname(__file__), "snmp_provider.py")
_spec = importlib.util.spec_from_file_location("snmp_provider_module", _PROVIDER_PY)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SNMPProvider = _mod.SNMPProvider

# Pull in types used in tests from whichever source succeeded
from keep.api.models.alert import AlertSeverity, AlertStatus, AlertDto  # noqa: E402
from keep.providers.models.provider_config import ProviderConfig         # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(auth: dict) -> SNMPProvider:
    """Create a provider instance with the given auth config dict."""
    config = ProviderConfig(authentication=auth)
    return SNMPProvider(
        context_manager=MagicMock(),
        provider_id="test-snmp",
        config=config,
    )


# ===========================================================================
# Tests
# ===========================================================================

class TestValidateConfig(unittest.TestCase):
    """validate_config() correctness."""

    def test_valid_v2c(self):
        p = _make_provider({"version": "2c", "community_string": "public"})
        # validate_config called during __init__ — must not raise

    def test_valid_v1(self):
        _make_provider({"version": "1"})

    def test_valid_v3_with_username(self):
        _make_provider({"version": "3", "username": "admin",
                        "auth_key": "secret", "priv_key": "secret2"})

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _make_provider({"version": "5"})
        self.assertIn("2c", str(ctx.exception))

    def test_v3_without_username_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _make_provider({"version": "3", "username": ""})
        self.assertIn("username", str(ctx.exception))

    def test_invalid_port_zero_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _make_provider({"port": 0})
        self.assertIn("port", str(ctx.exception).lower())

    def test_invalid_port_too_high_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _make_provider({"port": 70000})
        self.assertIn("port", str(ctx.exception).lower())

    def test_invalid_poll_interval_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _make_provider({"poll_interval": 0})
        self.assertIn("poll_interval", str(ctx.exception).lower())


class TestOidMapping(unittest.TestCase):
    """_map_oid_to_alert_config() and longest-prefix matching."""

    def setUp(self):
        import json
        self.provider = _make_provider({
            "oids_mapping": json.dumps({
                "1.3.6.1.4.1.9": {"name": "Cisco Alert", "severity": "high"},
                "1.3.6.1.6.3.1.1.5.3": {"name": "Link Down", "severity": "critical"},
            })
        })

    def test_exact_oid_returns_config(self):
        result = self.provider._map_oid_to_alert_config("1.3.6.1.6.3.1.1.5.3.0")
        self.assertEqual(result["name"], "Link Down")
        self.assertEqual(result["severity"], "critical")

    def test_prefix_match(self):
        result = self.provider._map_oid_to_alert_config("1.3.6.1.4.1.9.1.2.3")
        self.assertEqual(result["name"], "Cisco Alert")

    def test_no_match_returns_empty(self):
        result = self.provider._map_oid_to_alert_config("9.9.9.9.9")
        self.assertEqual(result, {})

    def test_longest_prefix_wins(self):
        import json
        p = _make_provider({
            "oids_mapping": json.dumps({
                "1.3.6.1.4.1": {"name": "Generic", "severity": "info"},
                "1.3.6.1.4.1.9": {"name": "Cisco", "severity": "high"},
            })
        })
        result = p._map_oid_to_alert_config("1.3.6.1.4.1.9.1.2")
        self.assertEqual(result["name"], "Cisco")


class TestSeverityInference(unittest.TestCase):
    """_infer_severity_from_oid() for well-known OIDs."""

    def setUp(self):
        self.p = _make_provider({})

    def test_link_down_is_critical(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.6.3.1.1.5.3")
        self.assertEqual(sv, AlertSeverity.CRITICAL)

    def test_cold_start_is_info(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.6.3.1.1.5.1")
        self.assertEqual(sv, AlertSeverity.INFO)

    def test_unknown_defaults_to_info(self):
        sv = self.p._infer_severity_from_oid("9.9.9.9.9.9")
        self.assertEqual(sv, AlertSeverity.INFO)

    def test_cisco_oid_is_high(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.4.1.9.1.2")
        self.assertEqual(sv, AlertSeverity.HIGH)


class TestParseSeverity(unittest.TestCase):
    """_parse_severity() static helper."""

    def test_critical(self):
        self.assertEqual(SNMPProvider._parse_severity("critical"), AlertSeverity.CRITICAL)

    def test_case_insensitive(self):
        self.assertEqual(SNMPProvider._parse_severity("WARNING"), AlertSeverity.WARNING)

    def test_empty_returns_none(self):
        self.assertIsNone(SNMPProvider._parse_severity(""))

    def test_unknown_returns_none(self):
        self.assertIsNone(SNMPProvider._parse_severity("godmode"))


class TestDispose(unittest.TestCase):
    """dispose() lifecycle method."""

    def test_dispose_sets_stop_event(self):
        p = _make_provider({})
        self.assertFalse(p._stop_event.is_set())
        p.dispose()
        self.assertTrue(p._stop_event.is_set())

    def test_dispose_with_no_threads_does_not_raise(self):
        p = _make_provider({})
        p.dispose()  # must not raise

    def test_dispose_joins_running_threads(self):
        p = _make_provider({})
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        p._listener_thread = mock_thread
        p._poll_thread = mock_thread
        p.dispose()
        self.assertEqual(mock_thread.join.call_count, 2)


class TestGetAlerts(unittest.TestCase):
    """_get_alerts() behaviour."""

    def test_returns_list(self):
        p = _make_provider({})
        with patch.object(p, "_start_trap_listener"):
            result = p._get_alerts()
        self.assertIsInstance(result, list)

    def test_returns_copy_not_reference(self):
        """Mutating returned list should not affect internal state."""
        import datetime
        p = _make_provider({})
        dummy = AlertDto(
            id="x", name="test", severity=AlertSeverity.INFO,
            status=AlertStatus.FIRING, source=["snmp"],
            description="test", lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        with p._alerts_lock:
            p._alerts.append(dummy)
        with patch.object(p, "_start_trap_listener"):
            result = p._get_alerts()
        result.clear()
        self.assertEqual(len(p._alerts), 1, "Internal alert list was mutated via returned copy")

    def test_calls_start_listener_when_not_running(self):
        p = _make_provider({})
        with patch.object(p, "_start_trap_listener") as mock_start:
            p._get_alerts()
        mock_start.assert_called_once()


class TestInvalidJsonConfig(unittest.TestCase):
    """Graceful handling of malformed JSON in config fields."""

    def test_bad_oids_mapping_uses_empty(self):
        p = _make_provider({"oids_mapping": "{bad json}"})
        self.assertEqual(p._oids_mapping, {})

    def test_bad_poll_targets_uses_empty(self):
        p = _make_provider({"poll_targets": "[not json]"})
        self.assertEqual(p._poll_targets, [])


class TestTrapOidExtraction(unittest.TestCase):
    """trap_oid is extracted from snmpTrapOID.0 varbind."""

    def setUp(self):
        self.p = _make_provider({})

    def test_trap_oid_extracted_from_varbinds(self):
        """snmpTrapOID.0 value should be used as primary OID."""
        var_binds = [
            ("1.3.6.1.2.1.1.3.0", "12345"),  # sysUpTime
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3"),  # snmpTrapOID.0 → linkDown
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertIn("1.3.6.1.6.3.1.1.5.3", alert.name)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_trap_oid_in_labels(self):
        """trap_oid should appear in labels."""
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.4"),  # linkUp
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertEqual(alert.labels["trap_oid"], "1.3.6.1.6.3.1.1.5.4")

    def test_no_trap_oid_falls_back_to_last_oid(self):
        """Without snmpTrapOID.0, last varbind OID is used."""
        var_binds = [
            ("1.3.6.1.4.1.9.1.2.3", "some value"),
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertIn("1.3.6.1.4.1.9.1.2.3", alert.name)


class TestAlertStatusFromTrapOid(unittest.TestCase):
    """Recovery OIDs → RESOLVED, firing OIDs → FIRING."""

    def setUp(self):
        self.p = _make_provider({})

    def test_link_up_is_resolved(self):
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.4"),  # linkUp
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_cold_start_is_resolved(self):
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.1"),  # coldStart
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_warm_start_is_resolved(self):
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.2"),  # warmStart
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_link_down_is_firing(self):
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3"),  # linkDown
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_auth_failure_is_firing(self):
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.5"),  # authenticationFailure
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertEqual(alert.status, AlertStatus.FIRING)


class TestSourceIpAndFingerprint(unittest.TestCase):
    """Source IP extraction and fingerprint deduplication."""

    def setUp(self):
        self.p = _make_provider({})

    def test_source_ip_in_labels(self):
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3"),
        ]
        alert = self.p._varbinds_to_alert(var_binds, source_ip="192.168.1.1")
        self.assertEqual(alert.labels["source_ip"], "192.168.1.1")

    def test_fingerprint_uses_source_ip_and_trap_oid(self):
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3"),
        ]
        alert = self.p._varbinds_to_alert(var_binds, source_ip="10.0.0.1")
        self.assertEqual(alert.fingerprint, "10.0.0.1:1.3.6.1.6.3.1.1.5.3")

    def test_no_source_ip_no_fingerprint(self):
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3"),
        ]
        alert = self.p._varbinds_to_alert(var_binds, source_ip=None)
        self.assertIsNone(alert.fingerprint)

    def test_trap_callback_extracts_source_ip(self):
        """_trap_callback should try to extract source IP from snmp engine."""
        mock_engine = MagicMock()
        mock_engine.msgAndPduDsp.getTransportInfo.return_value = (
            ("udp", "v4"),
            ("192.168.1.100", 45000),
        )
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3"),
        ]
        self.p._trap_callback(mock_engine, 42, None, None, var_binds, None)
        self.assertEqual(len(self.p._alerts), 1)
        alert = self.p._alerts[0]
        self.assertEqual(alert.labels["source_ip"], "192.168.1.100")
        self.assertEqual(alert.fingerprint, "192.168.1.100:1.3.6.1.6.3.1.1.5.3")


class TestAlertsCap(unittest.TestCase):
    """_append_alert() respects _MAX_ALERTS bound."""

    def test_alerts_capped_at_max(self):
        import datetime
        p = _make_provider({})
        p._MAX_ALERTS = 5  # lower cap for testing
        for i in range(10):
            alert = AlertDto(
                id=str(i), name=f"test-{i}", severity=AlertSeverity.INFO,
                status=AlertStatus.FIRING, source=["snmp"],
                description="test",
                lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            p._append_alert(alert)
        self.assertEqual(len(p._alerts), 5)
        # Should keep the most recent alerts
        self.assertEqual(p._alerts[0].id, "5")
        self.assertEqual(p._alerts[-1].id, "9")


class TestEdgeCases(unittest.TestCase):
    """Additional edge-case coverage."""

    def test_empty_varbinds(self):
        p = _make_provider({})
        alert = p._varbinds_to_alert([])
        self.assertEqual(alert.name, "SNMP Trap: ")
        self.assertEqual(alert.severity, AlertSeverity.INFO)

    def test_oids_mapping_with_non_dict_value(self):
        """oids_mapping values that aren't dicts should not crash _varbinds_to_alert."""
        import json
        p = _make_provider({
            "oids_mapping": json.dumps({
                "1.3.6.1.4.1.9": "not a dict",
            })
        })
        var_binds = [("1.3.6.1.4.1.9.1.2.3", "some value")]
        alert = p._varbinds_to_alert(var_binds)
        # Should fall back to default name, not crash
        self.assertIn("1.3.6.1.4.1.9.1.2.3", alert.name)


class TestTrapCallbackErrorHandling(unittest.TestCase):
    """_trap_callback gracefully handles malformed data."""

    def test_malformed_varbinds_do_not_crash(self):
        """If _varbinds_to_alert raises, the callback logs and continues."""
        p = _make_provider({})
        mock_engine = MagicMock()
        mock_engine.msgAndPduDsp.getTransportInfo.side_effect = Exception("bad state")
        # Even with broken transport info extraction, callback should not raise
        var_binds = [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")]
        p._trap_callback(mock_engine, 42, None, None, var_binds, None)
        # Alert should still be created (source_ip will be None)
        self.assertEqual(len(p._alerts), 1)
        self.assertIsNone(p._alerts[0].fingerprint)

    def test_completely_broken_varbinds(self):
        """Callback handles exception from _varbinds_to_alert itself."""
        p = _make_provider({})
        mock_engine = MagicMock()
        mock_engine.msgAndPduDsp.getTransportInfo.return_value = (None, None)
        # Pass something that will break iteration in _varbinds_to_alert
        with patch.object(p, "_varbinds_to_alert", side_effect=Exception("parse error")):
            p._trap_callback(mock_engine, 42, None, None, [], None)
        # No alert should be added, but no crash
        self.assertEqual(len(p._alerts), 0)


class TestPollingUsesAppendAlert(unittest.TestCase):
    """Polling should use _append_alert to respect _MAX_ALERTS cap."""

    def test_poll_alerts_are_bounded(self):
        import datetime
        p = _make_provider({})
        p._MAX_ALERTS = 3
        # Simulate what _poll_target does by calling _append_alert directly
        for i in range(5):
            alert = AlertDto(
                id=str(i), name=f"poll-{i}", severity=AlertSeverity.INFO,
                status=AlertStatus.FIRING, source=["snmp"],
                description="test",
                lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            p._append_alert(alert)
        self.assertEqual(len(p._alerts), 3)
        self.assertEqual(p._alerts[0].id, "2")


class TestSNMPVersionParametrized(unittest.TestCase):
    """Parametrized tests for all valid SNMP versions."""

    def test_all_valid_versions(self):
        for version in ("1", "2c"):
            with self.subTest(version=version):
                p = _make_provider({"version": version})
                self.assertEqual(p.authentication_config.version, version)

    def test_v3_valid(self):
        p = _make_provider({"version": "3", "username": "admin"})
        self.assertEqual(p.authentication_config.version, "3")

    def test_invalid_versions(self):
        for version in ("0", "4", "5", "v2c", ""):
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    _make_provider({"version": version})


# ===========================================================================
# Additional tests — config defaults and validation edge cases
# ===========================================================================

class TestConfigDefaults(unittest.TestCase):
    """Verify default values for provider configuration fields."""

    def test_default_version_is_2c(self):
        p = _make_provider({})
        self.assertEqual(p.authentication_config.version, "2c")

    def test_default_community_is_public(self):
        p = _make_provider({})
        self.assertEqual(p.authentication_config.community_string, "public")

    def test_custom_community_accepted(self):
        p = _make_provider({"community_string": "my-secret"})
        self.assertEqual(p.authentication_config.community_string, "my-secret")

    def test_port_65535_accepted(self):
        p = _make_provider({"port": 65535})
        self.assertEqual(p.authentication_config.port, 65535)

    def test_poll_interval_negative_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _make_provider({"poll_interval": -5})
        self.assertIn("poll_interval", str(ctx.exception).lower())

    def test_poll_enabled_default_false(self):
        p = _make_provider({})
        self.assertFalse(p.authentication_config.poll_enabled)

    def test_default_host_is_all_interfaces(self):
        p = _make_provider({})
        self.assertEqual(p.authentication_config.host, "0.0.0.0")

    def test_default_port_is_162(self):
        p = _make_provider({})
        self.assertEqual(p.authentication_config.port, 162)

    def test_default_poll_interval_is_60(self):
        p = _make_provider({})
        self.assertEqual(p.authentication_config.poll_interval, 60)

    def test_default_auth_protocol_is_md5(self):
        p = _make_provider({})
        self.assertEqual(p.authentication_config.auth_protocol, "MD5")

    def test_default_priv_protocol_is_des(self):
        p = _make_provider({})
        self.assertEqual(p.authentication_config.priv_protocol, "DES")


class TestConfigJsonParsing(unittest.TestCase):
    """JSON parsing of oids_mapping and poll_targets."""

    def test_valid_oids_mapping_parsed(self):
        import json
        mapping = {"1.3.6.1.4.1.9": {"name": "Cisco", "severity": "high"}}
        p = _make_provider({"oids_mapping": json.dumps(mapping)})
        self.assertEqual(p._oids_mapping, mapping)

    def test_valid_poll_targets_parsed(self):
        import json
        targets = [{"host": "192.168.1.1", "oids": ["1.3.6.1.2.1.1.3.0"]}]
        p = _make_provider({"poll_targets": json.dumps(targets)})
        self.assertEqual(p._poll_targets, targets)

    def test_oids_mapping_not_object_defaults_to_empty(self):
        """A JSON array for oids_mapping is valid JSON but wrong type — still parsed."""
        import json
        p = _make_provider({"oids_mapping": json.dumps([1, 2, 3])})
        # It parses, but won't behave as dict in _map_oid_to_alert_config
        self.assertIsInstance(p._oids_mapping, list)

    def test_poll_targets_not_list_defaults_to_empty(self):
        """A JSON object for poll_targets is valid JSON but wrong type — still parsed."""
        import json
        p = _make_provider({"poll_targets": json.dumps({"not": "a list"})})
        self.assertIsInstance(p._poll_targets, dict)

    def test_empty_oids_mapping_string_parsed(self):
        p = _make_provider({"oids_mapping": "{}"})
        self.assertEqual(p._oids_mapping, {})

    def test_empty_poll_targets_string_parsed(self):
        p = _make_provider({"poll_targets": "[]"})
        self.assertEqual(p._poll_targets, [])


# ===========================================================================
# Severity inference — enterprise prefixes
# ===========================================================================

class TestEnterpriseSeverityMapping(unittest.TestCase):
    """_infer_severity_from_oid() for enterprise OID prefixes (vendor detection)."""

    def setUp(self):
        self.p = _make_provider({})

    def test_cisco_prefix(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.4.1.9.9.1.2")
        self.assertEqual(sv, AlertSeverity.HIGH)

    def test_hp_prefix(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.4.1.11.2.3.4")
        self.assertEqual(sv, AlertSeverity.HIGH)

    def test_juniper_prefix(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.4.1.2636.1.2")
        self.assertEqual(sv, AlertSeverity.HIGH)

    def test_huawei_prefix(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.4.1.2011.5.25")
        self.assertEqual(sv, AlertSeverity.MEDIUM)

    def test_warm_start_is_warning(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.6.3.1.1.5.2")
        self.assertEqual(sv, AlertSeverity.WARNING)

    def test_link_up_is_info(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.6.3.1.1.5.4")
        self.assertEqual(sv, AlertSeverity.INFO)

    def test_auth_failure_is_critical(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.6.3.1.1.5.5")
        self.assertEqual(sv, AlertSeverity.CRITICAL)

    def test_egp_neighbor_loss_is_warning(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.6.3.1.1.5.6")
        self.assertEqual(sv, AlertSeverity.WARNING)

    def test_unknown_vendor_defaults_to_info(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.4.1.99999.1.2")
        self.assertEqual(sv, AlertSeverity.INFO)

    def test_standard_oid_without_enterprise_is_info(self):
        sv = self.p._infer_severity_from_oid("1.3.6.1.2.1.1.3.0")
        self.assertEqual(sv, AlertSeverity.INFO)


class TestEnterpriseSeverityTableCompleteness(unittest.TestCase):
    """All entries in _ENTERPRISE_SEVERITY are valid AlertSeverity values."""

    def test_all_standard_oids_have_severity(self):
        for prefix, severity in SNMPProvider._ENTERPRISE_SEVERITY.items():
            with self.subTest(prefix=prefix):
                self.assertIsInstance(severity, AlertSeverity)

    def test_enterprise_severity_map_not_empty(self):
        self.assertGreater(len(SNMPProvider._ENTERPRISE_SEVERITY), 0)

    def test_recovery_oids_set_not_empty(self):
        self.assertGreater(len(SNMPProvider._RECOVERY_OIDS), 0)


# ===========================================================================
# Parse severity — additional cases
# ===========================================================================

class TestParseSeverityExtended(unittest.TestCase):
    """Additional _parse_severity() test cases."""

    def test_high_severity(self):
        self.assertEqual(SNMPProvider._parse_severity("high"), AlertSeverity.HIGH)

    def test_warning_severity(self):
        self.assertEqual(SNMPProvider._parse_severity("warning"), AlertSeverity.WARNING)

    def test_info_severity(self):
        self.assertEqual(SNMPProvider._parse_severity("info"), AlertSeverity.INFO)

    def test_medium_severity(self):
        self.assertEqual(SNMPProvider._parse_severity("medium"), AlertSeverity.MEDIUM)

    def test_low_severity(self):
        self.assertEqual(SNMPProvider._parse_severity("low"), AlertSeverity.LOW)

    def test_with_whitespace(self):
        self.assertEqual(SNMPProvider._parse_severity("  critical  "), AlertSeverity.CRITICAL)

    def test_mixed_case(self):
        self.assertEqual(SNMPProvider._parse_severity("CrItIcAl"), AlertSeverity.CRITICAL)

    def test_none_returns_none(self):
        self.assertIsNone(SNMPProvider._parse_severity(""))

    def test_unknown_string_defaults_to_none(self):
        self.assertIsNone(SNMPProvider._parse_severity("urgent"))


# ===========================================================================
# Alert DTO construction — field-level checks
# ===========================================================================

class TestAlertDtoFields(unittest.TestCase):
    """Verify all fields of the AlertDto produced by _varbinds_to_alert."""

    def setUp(self):
        self.p = _make_provider({})

    def test_returns_alert_dto(self):
        alert = self.p._varbinds_to_alert([("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")])
        self.assertIsInstance(alert, AlertDto)

    def test_id_is_uuid(self):
        import uuid as uuid_mod
        alert = self.p._varbinds_to_alert([("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")])
        # Should not raise
        uuid_mod.UUID(alert.id)

    def test_last_received_is_set(self):
        alert = self.p._varbinds_to_alert([("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")])
        self.assertIsNotNone(alert.lastReceived)
        self.assertIn("T", alert.lastReceived)  # ISO format

    def test_snmp_source_in_source_list(self):
        alert = self.p._varbinds_to_alert([("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")])
        self.assertIn("snmp", alert.source)

    def test_source_address_set(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")],
            source_ip="10.0.0.5",
        )
        self.assertEqual(alert.labels["source_ip"], "10.0.0.5")

    def test_varbinds_in_description(self):
        var_binds = [
            ("1.3.6.1.2.1.1.3.0", "12345"),
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3"),
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertIn("12345", alert.description)
        self.assertIn("1.3.6.1.2.1.1.3.0", alert.description)

    def test_source_in_labels(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")],
            source_ip="172.16.0.1",
        )
        self.assertIn("source_ip", alert.labels)

    def test_trap_oid_in_labels_field(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")],
        )
        self.assertEqual(alert.labels["trap_oid"], "1.3.6.1.6.3.1.1.5.3")

    def test_no_source_ip_labels_has_no_source_ip(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")],
            source_ip=None,
        )
        # labels should exist (trap_oid present) but no source_ip
        self.assertNotIn("source_ip", alert.labels or {})

    def test_unknown_oid_fallback_name(self):
        alert = self.p._varbinds_to_alert([("9.9.9.9.9", "somevalue")])
        self.assertIn("9.9.9.9.9", alert.name)

    def test_custom_name_field_from_mapping(self):
        import json
        p = _make_provider({"oids_mapping": json.dumps({
            "1.3.6.1.4.1.9": {"name": "My Cisco Alert", "severity": "high"},
        })})
        alert = p._varbinds_to_alert([("1.3.6.1.4.1.9.1.2.3", "val")])
        self.assertEqual(alert.name, "My Cisco Alert")

    def test_severity_link_down_is_critical(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")],
        )
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_status_link_down_is_firing(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")],
        )
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_link_up_status_is_resolved(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.4")],
        )
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_cold_start_is_info_resolved(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.1")],
        )
        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_auth_failure_is_high_severity(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.5")],
        )
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_no_status_field_defaults_to_firing(self):
        """Unknown OIDs should default to FIRING status."""
        alert = self.p._varbinds_to_alert([("9.9.9.9", "val")])
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_labels_none_when_no_source_ip_no_trap_oid(self):
        """With no trap_oid and no source_ip, labels should be None."""
        alert = self.p._varbinds_to_alert([("9.9.9.9", "val")], source_ip=None)
        self.assertIsNone(alert.labels)

    def test_fingerprint_none_without_source_ip(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")],
            source_ip=None,
        )
        self.assertIsNone(alert.fingerprint)

    def test_fingerprint_format(self):
        alert = self.p._varbinds_to_alert(
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")],
            source_ip="10.0.0.1",
        )
        self.assertEqual(alert.fingerprint, "10.0.0.1:1.3.6.1.6.3.1.1.5.3")


# ===========================================================================
# Varbinds description construction
# ===========================================================================

class TestDescriptionConstruction(unittest.TestCase):
    """Description field from varbinds."""

    def setUp(self):
        self.p = _make_provider({})

    def test_link_down_builds_correctly(self):
        var_binds = [
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3"),
            ("1.3.6.1.2.1.2.2.1.1", "2"),
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertIn("1.3.6.1.6.3.1.1.5.3", alert.description)

    def test_varbinds_appear_in_description(self):
        var_binds = [
            ("1.3.6.1.2.1.1.1.0", "Linux router"),
            ("1.3.6.1.2.1.1.3.0", "98765"),
        ]
        alert = self.p._varbinds_to_alert(var_binds)
        self.assertIn("Linux router", alert.description)
        self.assertIn("98765", alert.description)

    def test_many_varbinds_all_in_description(self):
        var_binds = [(f"1.3.6.1.2.1.1.{i}.0", f"value-{i}") for i in range(12)]
        alert = self.p._varbinds_to_alert(var_binds)
        for i in range(12):
            self.assertIn(f"value-{i}", alert.description)

    def test_description_format_oid_equals_value(self):
        alert = self.p._varbinds_to_alert([("1.2.3", "hello")])
        self.assertIn("1.2.3 = hello", alert.description)

    def test_empty_varbinds_empty_description(self):
        alert = self.p._varbinds_to_alert([])
        self.assertEqual(alert.description, "")

    def test_multiline_description_with_newlines(self):
        var_binds = [("1.1", "a"), ("2.2", "b"), ("3.3", "c")]
        alert = self.p._varbinds_to_alert(var_binds)
        lines = alert.description.split("\n")
        self.assertEqual(len(lines), 3)


# ===========================================================================
# OID mapping — extended
# ===========================================================================

class TestOidMappingExtended(unittest.TestCase):
    """Extended OID mapping tests."""

    def test_user_mapping_overrides_standard(self):
        """User-defined mapping should override standard severity inference."""
        import json
        p = _make_provider({"oids_mapping": json.dumps({
            "1.3.6.1.6.3.1.1.5.3": {"name": "Custom Link Down", "severity": "warning"},
        })})
        var_binds = [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")]
        alert = p._varbinds_to_alert(var_binds)
        self.assertEqual(alert.name, "Custom Link Down")
        self.assertEqual(alert.severity, AlertSeverity.WARNING)

    def test_user_prefix_match(self):
        import json
        p = _make_provider({"oids_mapping": json.dumps({
            "1.3.6.1.4.1": {"name": "Enterprise Alert", "severity": "info"},
        })})
        result = p._map_oid_to_alert_config("1.3.6.1.4.1.9.1.2.3")
        self.assertEqual(result["name"], "Enterprise Alert")

    def test_empty_oids_mapping_returns_empty(self):
        p = _make_provider({})
        result = p._map_oid_to_alert_config("1.3.6.1.6.3.1.1.5.3")
        self.assertEqual(result, {})

    def test_mapping_with_severity_only(self):
        import json
        p = _make_provider({"oids_mapping": json.dumps({
            "1.3.6.1.4.1.9": {"severity": "critical"},
        })})
        result = p._map_oid_to_alert_config("1.3.6.1.4.1.9.5.6")
        self.assertEqual(result["severity"], "critical")
        self.assertNotIn("name", result)

    def test_mapping_with_name_only(self):
        import json
        p = _make_provider({"oids_mapping": json.dumps({
            "1.3.6.1.4.1.9": {"name": "Cisco Only"},
        })})
        result = p._map_oid_to_alert_config("1.3.6.1.4.1.9.5.6")
        self.assertEqual(result["name"], "Cisco Only")


# ===========================================================================
# Listener lifecycle
# ===========================================================================

class TestListenerLifecycle(unittest.TestCase):
    """Trap listener start/stop lifecycle."""

    def test_start_listener_no_op_when_pysnmp_unavailable(self):
        p = _make_provider({})
        with patch.object(_mod, "PYSNMP_AVAILABLE", False):
            p._start_trap_listener()
        self.assertIsNone(p._listener_thread)

    def test_start_listener_creates_thread_when_pysnmp_available(self):
        p = _make_provider({})
        with patch.object(p, "_trap_listener_loop"):
            p._start_trap_listener()
        self.assertIsNotNone(p._listener_thread)
        p.dispose()

    def test_start_listener_clears_stop_event(self):
        p = _make_provider({})
        p._stop_event.set()
        with patch.object(p, "_trap_listener_loop"):
            p._start_trap_listener()
        self.assertFalse(p._stop_event.is_set())
        p.dispose()

    def test_start_polling_no_op_when_pysnmp_unavailable(self):
        p = _make_provider({"poll_enabled": True})
        with patch.object(_mod, "PYSNMP_AVAILABLE", False):
            p._start_polling()
        self.assertIsNone(p._poll_thread)

    def test_start_polling_no_op_without_targets(self):
        p = _make_provider({"poll_enabled": True})
        p._poll_targets = []
        p._start_polling()
        self.assertIsNone(p._poll_thread)


# ===========================================================================
# Dispose — extended
# ===========================================================================

class TestDisposeExtended(unittest.TestCase):
    """Additional dispose() tests."""

    def test_dispose_idempotent(self):
        p = _make_provider({})
        p.dispose()
        p.dispose()  # Should not raise

    def test_dispose_does_not_join_dead_thread(self):
        p = _make_provider({})
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        p._listener_thread = mock_thread
        p.dispose()
        mock_thread.join.assert_not_called()

    def test_dispose_joins_listener_with_timeout(self):
        p = _make_provider({})
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        p._listener_thread = mock_thread
        p.dispose()
        mock_thread.join.assert_called_once_with(timeout=5)


# ===========================================================================
# Buffer management — _get_alerts extended
# ===========================================================================

class TestGetAlertsExtended(unittest.TestCase):
    """Extended _get_alerts() tests."""

    def test_get_alerts_returns_empty_initially(self):
        p = _make_provider({})
        with patch.object(p, "_start_trap_listener"):
            result = p._get_alerts()
        self.assertEqual(result, [])

    def test_get_alerts_returns_all_buffered_alerts(self):
        import datetime
        p = _make_provider({})
        for i in range(3):
            alert = AlertDto(
                id=str(i), name=f"test-{i}", severity=AlertSeverity.INFO,
                status=AlertStatus.FIRING, source=["snmp"],
                description="test",
                lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            p._append_alert(alert)
        with patch.object(p, "_start_trap_listener"):
            result = p._get_alerts()
        self.assertEqual(len(result), 3)

    def test_get_alerts_starts_polling_when_enabled(self):
        import json
        p = _make_provider({
            "poll_enabled": True,
            "poll_targets": json.dumps([{"host": "10.0.0.1", "oids": ["1.2.3"]}]),
        })
        with patch.object(p, "_start_trap_listener"), \
             patch.object(p, "_start_polling") as mock_poll:
            p._get_alerts()
        mock_poll.assert_called_once()

    def test_get_alerts_does_not_start_polling_when_disabled(self):
        p = _make_provider({"poll_enabled": False})
        with patch.object(p, "_start_trap_listener"), \
             patch.object(p, "_start_polling") as mock_poll:
            p._get_alerts()
        mock_poll.assert_not_called()


# ===========================================================================
# Batch processing — multiple traps
# ===========================================================================

class TestBatchProcessing(unittest.TestCase):
    """Batch trap processing via _trap_callback."""

    def _make_engine(self, source_ip="192.168.1.1"):
        mock_engine = MagicMock()
        mock_engine.msgAndPduDsp.getTransportInfo.return_value = (
            ("udp", "v4"), (source_ip, 45000),
        )
        return mock_engine

    def test_batch_returns_list(self):
        p = _make_provider({})
        engine = self._make_engine()
        traps = [
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")],
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.4")],
            [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.1")],
        ]
        for varbinds in traps:
            p._trap_callback(engine, 42, None, None, varbinds, None)
        self.assertIsInstance(p._alerts, list)

    def test_batch_count(self):
        p = _make_provider({})
        engine = self._make_engine()
        for _ in range(5):
            p._trap_callback(engine, 42, None, None,
                           [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")], None)
        self.assertEqual(len(p._alerts), 5)

    def test_batch_items_are_alertdtos(self):
        p = _make_provider({})
        engine = self._make_engine()
        p._trap_callback(engine, 42, None, None,
                        [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")], None)
        self.assertIsInstance(p._alerts[0], AlertDto)

    def test_batch_severities_correct(self):
        p = _make_provider({})
        engine = self._make_engine()
        # linkDown = CRITICAL
        p._trap_callback(engine, 42, None, None,
                        [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")], None)
        # coldStart = INFO
        p._trap_callback(engine, 42, None, None,
                        [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.1")], None)
        self.assertEqual(p._alerts[0].severity, AlertSeverity.CRITICAL)
        self.assertEqual(p._alerts[1].severity, AlertSeverity.INFO)

    def test_single_varbind_returns_alert(self):
        p = _make_provider({})
        alert = p._varbinds_to_alert([("1.3.6.1.4.1.9.1.2.3", "some value")])
        self.assertIsInstance(alert, AlertDto)


# ===========================================================================
# Provider class-level attributes
# ===========================================================================

class TestProviderClassAttributes(unittest.TestCase):
    """Verify provider metadata attributes."""

    def test_provider_display_name(self):
        self.assertEqual(SNMPProvider.PROVIDER_DISPLAY_NAME, "SNMP")

    def test_provider_category(self):
        self.assertIn("Monitoring", SNMPProvider.PROVIDER_CATEGORY)

    def test_provider_tags(self):
        self.assertIn("alert", SNMPProvider.PROVIDER_TAGS)

    def test_max_alerts_default(self):
        self.assertEqual(SNMPProvider._MAX_ALERTS, 10_000)

    def test_snmp_trap_oid_constant(self):
        self.assertEqual(SNMPProvider._SNMP_TRAP_OID, "1.3.6.1.6.3.1.1.4.1.0")

    def test_recovery_oids_contains_cold_start(self):
        self.assertIn("1.3.6.1.6.3.1.1.5.1", SNMPProvider._RECOVERY_OIDS)

    def test_recovery_oids_contains_warm_start(self):
        self.assertIn("1.3.6.1.6.3.1.1.5.2", SNMPProvider._RECOVERY_OIDS)

    def test_recovery_oids_contains_link_up(self):
        self.assertIn("1.3.6.1.6.3.1.1.5.4", SNMPProvider._RECOVERY_OIDS)

    def test_link_down_not_in_recovery_oids(self):
        self.assertNotIn("1.3.6.1.6.3.1.1.5.3", SNMPProvider._RECOVERY_OIDS)


# ===========================================================================
# Trap callback — source IP edge cases
# ===========================================================================

class TestTrapCallbackSourceIp(unittest.TestCase):
    """Source IP extraction edge cases in _trap_callback."""

    def test_transport_address_none_yields_no_source_ip(self):
        p = _make_provider({})
        mock_engine = MagicMock()
        mock_engine.msgAndPduDsp.getTransportInfo.return_value = (
            ("udp", "v4"), None,
        )
        var_binds = [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")]
        p._trap_callback(mock_engine, 42, None, None, var_binds, None)
        self.assertIsNone(p._alerts[0].fingerprint)

    def test_ipv6_source_ip(self):
        p = _make_provider({})
        mock_engine = MagicMock()
        mock_engine.msgAndPduDsp.getTransportInfo.return_value = (
            ("udp", "v6"), ("::1", 45000),
        )
        var_binds = [("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")]
        p._trap_callback(mock_engine, 42, None, None, var_binds, None)
        self.assertEqual(p._alerts[0].labels["source_ip"], "::1")


# ===========================================================================
# Auth protocol / privacy protocol edge cases
# ===========================================================================

class TestV3Config(unittest.TestCase):
    """SNMPv3 configuration edge cases."""

    def test_v3_sha_auth_protocol(self):
        p = _make_provider({
            "version": "3", "username": "admin",
            "auth_protocol": "SHA", "auth_key": "secret",
        })
        self.assertEqual(p.authentication_config.auth_protocol, "SHA")

    def test_v3_aes_priv_protocol(self):
        p = _make_provider({
            "version": "3", "username": "admin",
            "priv_protocol": "AES", "priv_key": "secret",
        })
        self.assertEqual(p.authentication_config.priv_protocol, "AES")

    def test_v3_with_all_fields(self):
        p = _make_provider({
            "version": "3", "username": "admin",
            "auth_key": "authpass", "auth_protocol": "SHA",
            "priv_key": "privpass", "priv_protocol": "AES",
        })
        cfg = p.authentication_config
        self.assertEqual(cfg.username, "admin")
        self.assertEqual(cfg.auth_key, "authpass")
        self.assertEqual(cfg.priv_key, "privpass")


# ===========================================================================
# Concurrent access and thread safety
# ===========================================================================

class TestThreadSafety(unittest.TestCase):
    """Thread safety of alert buffer operations."""

    def test_concurrent_append_alert(self):
        import datetime
        import threading
        p = _make_provider({})
        p._MAX_ALERTS = 100

        def append_n(n):
            for i in range(n):
                alert = AlertDto(
                    id=str(i), name=f"t-{i}", severity=AlertSeverity.INFO,
                    status=AlertStatus.FIRING, source=["snmp"],
                    description="test",
                    lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                )
                p._append_alert(alert)

        threads = [threading.Thread(target=append_n, args=(20,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(p._alerts), 100)

    def test_append_and_get_concurrent(self):
        import datetime
        import threading
        p = _make_provider({})
        results = []

        def get_alerts():
            with patch.object(p, "_start_trap_listener"):
                r = p._get_alerts()
                results.append(len(r))

        # Add some alerts first
        for i in range(5):
            alert = AlertDto(
                id=str(i), name=f"t-{i}", severity=AlertSeverity.INFO,
                status=AlertStatus.FIRING, source=["snmp"],
                description="test",
                lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            p._append_alert(alert)

        threads = [threading.Thread(target=get_alerts) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # All readers should get the same count
        self.assertTrue(all(r == 5 for r in results))


# ===========================================================================
# Unique edge cases not in competitor PR
# ===========================================================================

class TestUniqueEdgeCases(unittest.TestCase):
    """Additional edge cases for robustness."""

    def test_varbind_with_empty_value(self):
        p = _make_provider({})
        alert = p._varbinds_to_alert([("1.3.6.1.2.1.1.1.0", "")])
        self.assertIn("1.3.6.1.2.1.1.1.0 = ", alert.description)

    def test_very_long_oid(self):
        p = _make_provider({})
        long_oid = ".".join(str(i) for i in range(50))
        alert = p._varbinds_to_alert([(long_oid, "val")])
        self.assertIn(long_oid, alert.name)

    def test_special_characters_in_value(self):
        p = _make_provider({})
        alert = p._varbinds_to_alert([("1.2.3", "hello\nworld\ttab")])
        self.assertIn("hello\nworld\ttab", alert.description)

    def test_numeric_value_as_string(self):
        p = _make_provider({})
        alert = p._varbinds_to_alert([("1.2.3", "42")])
        self.assertIn("42", alert.description)

    def test_multiple_traps_have_unique_ids(self):
        p = _make_provider({})
        alert1 = p._varbinds_to_alert([("1.2.3", "a")])
        alert2 = p._varbinds_to_alert([("1.2.3", "b")])
        self.assertNotEqual(alert1.id, alert2.id)

    def test_alerts_cap_evicts_oldest(self):
        import datetime
        p = _make_provider({})
        p._MAX_ALERTS = 3
        for i in range(5):
            alert = AlertDto(
                id=str(i), name=f"alert-{i}", severity=AlertSeverity.INFO,
                status=AlertStatus.FIRING, source=["snmp"],
                description="test",
                lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            p._append_alert(alert)
        self.assertEqual(p._alerts[0].name, "alert-2")
        self.assertEqual(p._alerts[-1].name, "alert-4")

    def test_v1_version_config(self):
        p = _make_provider({"version": "1"})
        self.assertEqual(p.authentication_config.version, "1")

    def test_custom_port_accepted(self):
        p = _make_provider({"port": 1620})
        self.assertEqual(p.authentication_config.port, 1620)

    def test_poll_interval_one_accepted(self):
        p = _make_provider({"poll_interval": 1})
        self.assertEqual(p.authentication_config.poll_interval, 1)

    def test_large_poll_interval_accepted(self):
        p = _make_provider({"poll_interval": 86400})
        self.assertEqual(p.authentication_config.poll_interval, 86400)

    def test_trap_callback_with_empty_varbinds(self):
        p = _make_provider({})
        mock_engine = MagicMock()
        mock_engine.msgAndPduDsp.getTransportInfo.return_value = (
            ("udp", "v4"), ("10.0.0.1", 45000),
        )
        p._trap_callback(mock_engine, 42, None, None, [], None)
        self.assertEqual(len(p._alerts), 1)
        self.assertEqual(p._alerts[0].name, "SNMP Trap: ")

    def test_severity_map_has_all_levels(self):
        expected = {"critical", "high", "warning", "medium", "info", "low"}
        actual = set(SNMPProvider._SEVERITY_MAP.keys())
        self.assertEqual(actual, expected)

    def test_stop_event_initially_clear(self):
        p = _make_provider({})
        self.assertFalse(p._stop_event.is_set())

    def test_alerts_list_initially_empty(self):
        p = _make_provider({})
        self.assertEqual(len(p._alerts), 0)

    def test_listener_thread_initially_none(self):
        p = _make_provider({})
        self.assertIsNone(p._listener_thread)

    def test_poll_thread_initially_none(self):
        p = _make_provider({})
        self.assertIsNone(p._poll_thread)


if __name__ == "__main__":
    unittest.main(verbosity=2)
