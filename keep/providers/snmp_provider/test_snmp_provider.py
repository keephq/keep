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

    udp = _m("pysnmp.carrier.asyncio.dgram.udp")
    udp.domainName = ("udp", "v4")

    engine_mod = _m("pysnmp.entity.engine")
    engine_mod.SnmpEngine = MagicMock()

    cfg_mod = _m("pysnmp.entity.config")
    for sym in ("addTransport", "addV1System", "addV3User",
                "usmHMACMD5AuthProtocol", "usmHMACSHAAuthProtocol",
                "usmDESPrivProtocol", "usmAesCfb128Protocol"):
        setattr(cfg_mod, sym, MagicMock())

    ntfrcv = _m("pysnmp.entity.rfc3413.ntfrcv")
    ntfrcv.NotificationReceiver = MagicMock()

    for name in ["pysnmp", "pysnmp.carrier", "pysnmp.carrier.asyncio",
                 "pysnmp.carrier.asyncio.dgram", "pysnmp.entity",
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
    """get_alerts() behaviour."""

    def test_returns_list(self):
        p = _make_provider({})
        with patch.object(p, "_start_trap_listener"):
            result = p.get_alerts()
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
            result = p.get_alerts()
        result.clear()
        self.assertEqual(len(p._alerts), 1, "Internal alert list was mutated via returned copy")

    def test_calls_start_listener_when_not_running(self):
        p = _make_provider({})
        with patch.object(p, "_start_trap_listener") as mock_start:
            p.get_alerts()
        mock_start.assert_called_once()


class TestInvalidJsonConfig(unittest.TestCase):
    """Graceful handling of malformed JSON in config fields."""

    def test_bad_oids_mapping_uses_empty(self):
        p = _make_provider({"oids_mapping": "{bad json}"})
        self.assertEqual(p._oids_mapping, {})

    def test_bad_poll_targets_uses_empty(self):
        p = _make_provider({"poll_targets": "[not json]"})
        self.assertEqual(p._poll_targets, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
