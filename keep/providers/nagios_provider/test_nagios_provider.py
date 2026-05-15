"""Unit tests for the Nagios provider — fully mocked."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from keep.api.models.alert import AlertSeverity, AlertStatus  # noqa: E402
from keep.providers.models.provider_config import ProviderConfig  # noqa: E402
from keep.providers.nagios_provider.nagios_provider import NagiosProvider  # noqa: E402


def _make_provider(verify_ssl: bool = False) -> NagiosProvider:
    ctx = MagicMock()
    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": "https://nagios.example.local",
            "api_key": "test-key-12345",
            "verify_ssl": verify_ssl,
        },
    )
    return NagiosProvider(ctx, provider_id="nagios-test", config=config)


class TestConfig(unittest.TestCase):
    def test_validate_config(self):
        p = _make_provider()
        self.assertEqual(p.authentication_config.api_key, "test-key-12345")
        self.assertFalse(p.authentication_config.verify_ssl)

    def test_url_construction(self):
        p = _make_provider()
        url = p._NagiosProvider__url("objects/hoststatus")
        self.assertEqual(
            url, "https://nagios.example.local/nagiosxi/api/v1/objects/hoststatus"
        )

    def test_params_include_apikey(self):
        p = _make_provider()
        params = p._NagiosProvider__params({"name": "myhost"})
        self.assertEqual(params["apikey"], "test-key-12345")
        self.assertEqual(params["name"], "myhost")


class TestHostAlertMapping(unittest.TestCase):
    def test_host_up_returns_none(self):
        p = _make_provider()
        self.assertIsNone(p._host_to_alert({"current_state": 0, "host_name": "x"}))

    def test_host_down_is_critical_firing(self):
        p = _make_provider()
        a = p._host_to_alert(
            {
                "current_state": 1,
                "host_name": "router-edge",
                "output": "PING CRITICAL - Packet loss = 100%",
                "host_object_id": 42,
                "last_check": "2026-05-15T10:00:00",
            }
        )
        self.assertIsNotNone(a)
        self.assertEqual(a.severity, AlertSeverity.CRITICAL)
        self.assertEqual(a.status, AlertStatus.FIRING)
        self.assertEqual(a.id, "nagios-host-42")
        self.assertIn("router-edge", a.name)
        self.assertEqual(a.source, ["nagios"])

    def test_host_unreachable_is_high_firing(self):
        p = _make_provider()
        a = p._host_to_alert(
            {"current_state": 2, "host_name": "remote-db", "host_object_id": 99}
        )
        self.assertEqual(a.severity, AlertSeverity.HIGH)
        self.assertEqual(a.status, AlertStatus.FIRING)


class TestServiceAlertMapping(unittest.TestCase):
    def test_service_ok_returns_none(self):
        p = _make_provider()
        self.assertIsNone(
            p._service_to_alert(
                {"current_state": 0, "host_name": "h", "service_description": "s"}
            )
        )

    def test_service_warning(self):
        p = _make_provider()
        a = p._service_to_alert(
            {
                "current_state": 1,
                "host_name": "web-1",
                "service_description": "HTTP",
                "service_object_id": 100,
                "output": "HTTP WARNING: HTTP/1.1 200 OK - response time 2.5s",
            }
        )
        self.assertEqual(a.severity, AlertSeverity.WARNING)
        self.assertEqual(a.status, AlertStatus.FIRING)
        self.assertIn("HTTP", a.name)
        self.assertIn("web-1", a.name)

    def test_service_critical(self):
        p = _make_provider()
        a = p._service_to_alert(
            {
                "current_state": 2,
                "host_name": "web-1",
                "service_description": "Disk",
                "service_object_id": 101,
            }
        )
        self.assertEqual(a.severity, AlertSeverity.CRITICAL)
        self.assertEqual(a.status, AlertStatus.FIRING)

    def test_service_unknown(self):
        p = _make_provider()
        a = p._service_to_alert(
            {"current_state": 3, "host_name": "x", "service_description": "y", "service_object_id": 102}
        )
        self.assertEqual(a.severity, AlertSeverity.INFO)
        # Unknown still fires — operator should know about it.
        self.assertEqual(a.status, AlertStatus.FIRING)


class TestUnwrapRecords(unittest.TestCase):
    def test_bare_list(self):
        rows = NagiosProvider._unwrap_records(
            [{"host_name": "a"}, {"host_name": "b"}], "hoststatus"
        )
        self.assertEqual(len(rows), 2)

    def test_top_level_key(self):
        payload = {"recordcount": 1, "hoststatus": [{"host_name": "a"}]}
        rows = NagiosProvider._unwrap_records(payload, "hoststatus")
        self.assertEqual(len(rows), 1)

    def test_nested_key(self):
        payload = {
            "recordcount": 1,
            "hoststatus": {"host_status": [{"host_name": "a"}]},
        }
        rows = NagiosProvider._unwrap_records(payload, "hoststatus")
        self.assertEqual(rows, [{"host_name": "a"}])

    def test_empty(self):
        self.assertEqual(NagiosProvider._unwrap_records({}, "hoststatus"), [])


class TestHttp(unittest.TestCase):
    @patch("keep.providers.nagios_provider.nagios_provider.requests.get")
    def test_get_alerts_filters_ok_states(self, mock_get):
        # First call: host status. Second call: service status.
        mock_get.side_effect = [
            MagicMock(
                ok=True,
                json=lambda: {
                    "recordcount": 2,
                    "hoststatus": [
                        {"current_state": 0, "host_name": "ok-host", "host_object_id": 1},
                        {"current_state": 1, "host_name": "down-host", "host_object_id": 2, "output": "DOWN"},
                    ],
                },
            ),
            MagicMock(
                ok=True,
                json=lambda: {
                    "recordcount": 2,
                    "servicestatus": [
                        {
                            "current_state": 0,
                            "host_name": "x",
                            "service_description": "ok-svc",
                            "service_object_id": 10,
                        },
                        {
                            "current_state": 2,
                            "host_name": "x",
                            "service_description": "crit-svc",
                            "service_object_id": 11,
                            "output": "DISK CRITICAL",
                        },
                    ],
                },
            ),
        ]
        p = _make_provider()
        alerts = p._get_alerts()
        # ok-host + ok-svc are dropped (state 0); down-host + crit-svc survive.
        self.assertEqual(len(alerts), 2)
        names = sorted(a.name for a in alerts)
        self.assertEqual(names[0], "Host down-host")
        self.assertIn("crit-svc", names[1])

    @patch("keep.providers.nagios_provider.nagios_provider.requests.get")
    def test_validate_scopes_reports_failure(self, mock_get):
        mock_get.return_value = MagicMock(ok=False, status_code=401, text="bad key")
        scopes = _make_provider().validate_scopes()
        self.assertIn("Error validating scopes", scopes["authenticated"])


if __name__ == "__main__":
    unittest.main()
