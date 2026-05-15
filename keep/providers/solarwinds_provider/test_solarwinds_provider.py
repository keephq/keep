"""Unit tests for the SolarWinds provider — fully mocked, no live Orion needed."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Allow `keep...` imports when running the file directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from keep.api.models.alert import AlertSeverity, AlertStatus  # noqa: E402
from keep.providers.models.provider_config import ProviderConfig  # noqa: E402
from keep.providers.solarwinds_provider.solarwinds_provider import (  # noqa: E402
    SolarwindsProvider,
)


def _make_provider(verify_ssl: bool = False) -> SolarwindsProvider:
    ctx = MagicMock()
    config = ProviderConfig(
        description="SolarWinds Provider",
        authentication={
            "host_url": "https://orion.example.local:17774",
            "username": "svc-keep",
            "password": "supersecret",
            "verify_ssl": verify_ssl,
        },
    )
    return SolarwindsProvider(ctx, provider_id="solarwinds-test", config=config)


class TestSolarwindsProviderConfig(unittest.TestCase):
    def test_validate_config_parses_authentication(self):
        provider = _make_provider()
        # validate_config is called from BaseProvider.__init__; just check the parsed shape.
        cfg = provider.authentication_config
        self.assertEqual(cfg.username, "svc-keep")
        self.assertEqual(cfg.password, "supersecret")
        self.assertFalse(cfg.verify_ssl)

    def test_query_url_constructed_correctly(self):
        provider = _make_provider()
        # private method, validated via name-mangled accessor
        url = provider._SolarwindsProvider__query_url()
        self.assertEqual(
            url,
            "https://orion.example.local:17774/SolarWinds/InformationService/v3/Json/Query",
        )


class TestSolarwindsAlertMapping(unittest.TestCase):
    def test_row_to_alert_critical_firing(self):
        provider = _make_provider()
        row = {
            "AlertObjectID": 42,
            "AlertActiveID": 7,
            "Name": "Node Down",
            "Severity": 3,
            "Description": "Primary router is unreachable",
            "TriggeredDateTime": "2026-05-15T10:00:00Z",
            "AcknowledgedDateTime": None,
            "EntityCaption": "router-edge-01",
            "EntityType": "Orion.Nodes",
            "RelatedNodeCaption": "router-edge-01",
            "AlertNote": "",
        }
        alert = provider._row_to_alert(row)
        self.assertEqual(alert.name, "Node Down")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.id, "7")
        self.assertEqual(alert.source, ["solarwinds"])

    def test_row_to_alert_warning_acknowledged(self):
        provider = _make_provider()
        row = {
            "AlertObjectID": 42,
            "AlertActiveID": 8,
            "Name": "High CPU",
            "Severity": 2,
            "Description": "CPU > 90%",
            "TriggeredDateTime": "2026-05-15T11:00:00Z",
            "AcknowledgedDateTime": "2026-05-15T11:05:00Z",
            "EntityCaption": "db-primary",
            "EntityType": "Orion.Nodes",
            "RelatedNodeCaption": "db-primary",
        }
        alert = provider._row_to_alert(row)
        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED)

    def test_row_to_alert_unknown_severity_falls_back_to_info(self):
        provider = _make_provider()
        row = {
            "AlertObjectID": 1,
            "AlertActiveID": 2,
            "Name": "Weird",
            "Severity": 99,  # Outside the documented 0..4 range
            "TriggeredDateTime": "2026-05-15T11:00:00Z",
            "EntityCaption": "x",
            "EntityType": "Orion.Nodes",
            "Description": "",
        }
        alert = provider._row_to_alert(row)
        self.assertEqual(alert.severity, AlertSeverity.INFO)


class TestSolarwindsHttp(unittest.TestCase):
    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_get_alerts_executes_swql_against_alert_active(self, mock_get):
        # Mock SWIS response shape: { "results": [...] }
        mock_get.return_value = MagicMock(
            ok=True,
            json=lambda: {
                "results": [
                    {
                        "AlertObjectID": 1,
                        "AlertActiveID": 10,
                        "Name": "Test alert",
                        "Severity": 3,
                        "Description": "test",
                        "TriggeredDateTime": "2026-05-15T10:00:00Z",
                        "AcknowledgedDateTime": None,
                        "EntityCaption": "n1",
                        "EntityType": "Orion.Nodes",
                        "RelatedNodeCaption": "n1",
                        "AlertNote": "",
                    }
                ]
            },
        )
        provider = _make_provider()
        alerts = provider._get_alerts()

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].name, "Test alert")
        self.assertEqual(alerts[0].severity, AlertSeverity.CRITICAL)

        # Validate the SWQL targets Orion.AlertActive (vs. AlertHistory).
        args, kwargs = mock_get.call_args
        params = kwargs.get("params") or (args[1] if len(args) > 1 else {})
        swql = params.get("query", "")
        self.assertIn("Orion.AlertActive", swql)
        self.assertIn("Orion.AlertConfigurations", swql)

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_validate_scopes_authenticated_on_200(self, mock_get):
        mock_get.return_value = MagicMock(
            ok=True, json=lambda: {"results": [{"AlertObjectID": 1}]}
        )
        provider = _make_provider()
        scopes = provider.validate_scopes()
        self.assertEqual(scopes, {"authenticated": True})

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_validate_scopes_reports_error_on_failure(self, mock_get):
        mock_get.return_value = MagicMock(
            ok=False, status_code=401, text="unauthorized"
        )
        provider = _make_provider()
        scopes = provider.validate_scopes()
        self.assertIn("Error validating scopes", scopes["authenticated"])


if __name__ == "__main__":
    unittest.main()
