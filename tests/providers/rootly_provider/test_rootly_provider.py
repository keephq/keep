"""
Tests for the Rootly Provider.

Covers:
  - Configuration and authentication
  - Scope validation
  - Alert pulling from Rootly Alerts API
  - Incident pulling from Rootly Incidents API
  - Webhook event formatting (alert + incident events)
  - Severity and status mapping
  - Edge cases (empty data, missing fields, noise alerts)
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.rootly_provider.rootly_provider import (
    RootlyProvider,
    RootlyProviderAuthConfig,
)


def _create_provider(
    api_key="test-api-key",
    api_url="https://api.rootly.com",
    pull_incidents=True,
) -> RootlyProvider:
    """Helper to instantiate a provider with test config."""
    context_manager = MagicMock()
    context_manager.tenant_id = "test-tenant"

    config = ProviderConfig(
        authentication={
            "api_key": api_key,
            "api_url": api_url,
            "pull_incidents": pull_incidents,
        }
    )
    return RootlyProvider(context_manager, "test-provider", config)


def _make_rootly_alert(
    alert_id="alert-123",
    summary="High CPU usage on api-gateway",
    status="open",
    source="datadog",
    noise="not_noise",
    services=None,
    environments=None,
    labels=None,
) -> dict:
    """Create a mock Rootly alert in JSON:API format."""
    return {
        "id": alert_id,
        "type": "alerts",
        "attributes": {
            "short_id": f"ALT-{alert_id[-3:]}",
            "summary": summary,
            "description": f"Details for {summary}",
            "status": status,
            "source": source,
            "noise": noise,
            "created_at": "2026-03-18T10:00:00Z",
            "updated_at": "2026-03-18T10:05:00Z",
            "started_at": "2026-03-18T10:00:00Z",
            "ended_at": None,
            "external_url": f"https://rootly.com/alerts/{alert_id}",
            "deduplication_key": f"dedup-{alert_id}",
            "services": services or [{"name": "api-gateway"}],
            "environments": environments or [{"name": "production"}],
            "groups": [{"name": "platform-team"}],
            "labels": labels or [
                {"key": "severity", "value": "critical"},
                {"key": "team", "value": "platform"},
            ],
        },
    }


def _make_rootly_incident(
    incident_id="inc-456",
    title="Database outage in production",
    summary="MySQL primary is unreachable",
    status="started",
    severity="critical",
    services=None,
    environments=None,
) -> dict:
    """Create a mock Rootly incident in JSON:API format."""
    return {
        "id": incident_id,
        "type": "incidents",
        "attributes": {
            "title": title,
            "summary": summary,
            "status": status,
            "sequential_id": 42,
            "url": f"https://rootly.com/incidents/{incident_id}",
            "short_url": f"https://rtly.io/{incident_id}",
            "created_at": "2026-03-18T10:00:00Z",
            "updated_at": "2026-03-18T10:05:00Z",
            "started_at": "2026-03-18T10:01:00Z",
            "mitigated_at": None,
            "resolved_at": None,
            "severity": {
                "data": {
                    "attributes": {
                        "severity": severity,
                        "name": severity.capitalize(),
                    }
                }
            },
            "services": services or [
                {"data": {"attributes": {"name": "mysql-primary"}}}
            ],
            "environments": environments or [
                {"data": {"attributes": {"name": "production"}}}
            ],
            "labels": {},
            "slack_channel_name": "inc-database-outage",
        },
    }


class TestRootlyProviderConfig(unittest.TestCase):
    """Test provider configuration and initialization."""

    def test_basic_config(self):
        provider = _create_provider()
        self.assertEqual(provider.authentication_config.api_key, "test-api-key")
        self.assertEqual(
            provider.authentication_config.api_url, "https://api.rootly.com"
        )

    def test_pull_incidents_default(self):
        provider = _create_provider()
        self.assertTrue(provider.authentication_config.pull_incidents)

    def test_pull_incidents_disabled(self):
        provider = _create_provider(pull_incidents=False)
        self.assertFalse(provider.authentication_config.pull_incidents)

    def test_provider_display_name(self):
        self.assertEqual(RootlyProvider.PROVIDER_DISPLAY_NAME, "Rootly")

    def test_provider_category(self):
        self.assertIn("Incident Management", RootlyProvider.PROVIDER_CATEGORY)

    def test_provider_tags(self):
        self.assertIn("alert", RootlyProvider.PROVIDER_TAGS)

    def test_headers(self):
        provider = _create_provider(api_key="rootly-key-123")
        headers = provider._headers
        self.assertEqual(headers["Authorization"], "Bearer rootly-key-123")
        self.assertEqual(headers["Content-Type"], "application/vnd.api+json")

    def test_api_base_trailing_slash(self):
        provider = _create_provider(api_url="https://api.rootly.com/")
        self.assertEqual(provider._api_base, "https://api.rootly.com")


class TestScopeValidation(unittest.TestCase):
    """Test scope validation logic."""

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_all_scopes_valid(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"data": [], "meta": {}}),
        )

        provider = _create_provider()
        scopes = provider.validate_scopes()
        self.assertTrue(scopes["authenticated"])
        self.assertTrue(scopes["read_alerts"])
        self.assertTrue(scopes["read_incidents"])

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_auth_failure(self, mock_get):
        mock_get.return_value = MagicMock(status_code=401)

        provider = _create_provider()
        scopes = provider.validate_scopes()
        self.assertIn("invalid", scopes["authenticated"])

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_forbidden_alerts(self, mock_get):
        mock_get.side_effect = [
            MagicMock(status_code=403),  # alerts forbidden
        ]

        provider = _create_provider()
        scopes = provider.validate_scopes()
        self.assertTrue(scopes["authenticated"])
        self.assertIn("Insufficient", scopes["read_alerts"])


class TestPullAlerts(unittest.TestCase):
    """Test alert pulling from Rootly Alerts API."""

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_pull_alerts_basic(self, mock_get):
        alerts_data = [
            _make_rootly_alert(alert_id="a1", summary="Alert 1"),
            _make_rootly_alert(alert_id="a2", summary="Alert 2"),
        ]
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": alerts_data,
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider(pull_incidents=False)
        alerts = provider._get_alerts()
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0].name, "Alert 1")
        self.assertEqual(alerts[1].name, "Alert 2")

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_pull_alerts_noise_suppressed(self, mock_get):
        alert = _make_rootly_alert(noise="noise")
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [alert],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider(pull_incidents=False)
        alerts = provider._get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].status, AlertStatus.SUPPRESSED)

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_pull_alerts_api_error(self, mock_get):
        mock_get.return_value = MagicMock(ok=False, status_code=500)

        provider = _create_provider(pull_incidents=False)
        alerts = provider._get_alerts()
        self.assertEqual(len(alerts), 0)

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_pull_alerts_empty(self, mock_get):
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider(pull_incidents=False)
        alerts = provider._get_alerts()
        self.assertEqual(len(alerts), 0)

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_alert_service_extraction(self, mock_get):
        alert = _make_rootly_alert(
            services=[{"name": "api-gateway"}, {"name": "auth-service"}]
        )
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [alert],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider(pull_incidents=False)
        alerts = provider._get_alerts()
        self.assertIn("api-gateway", alerts[0].service)
        self.assertIn("auth-service", alerts[0].service)

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_alert_labels_extraction(self, mock_get):
        alert = _make_rootly_alert(
            labels=[
                {"key": "team", "value": "platform"},
                {"key": "region", "value": "us-east-1"},
            ]
        )
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [alert],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider(pull_incidents=False)
        alerts = provider._get_alerts()
        self.assertEqual(alerts[0].labels["team"], "platform")
        self.assertEqual(alerts[0].labels["region"], "us-east-1")

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_alert_fingerprint(self, mock_get):
        alert = _make_rootly_alert(alert_id="abc-123")
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [alert],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider(pull_incidents=False)
        alerts = provider._get_alerts()
        self.assertEqual(alerts[0].fingerprint, "rootly-alert-abc-123")


class TestPullIncidents(unittest.TestCase):
    """Test incident pulling from Rootly Incidents API."""

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_pull_incidents(self, mock_get):
        incidents = [
            _make_rootly_incident(incident_id="i1", title="Outage"),
            _make_rootly_incident(incident_id="i2", title="Degradation"),
        ]
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": incidents,
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider()
        alerts = provider._pull_incidents()
        self.assertEqual(len(alerts), 2)

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_incident_severity_critical(self, mock_get):
        incident = _make_rootly_incident(severity="critical")
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [incident],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider()
        alerts = provider._pull_incidents()
        self.assertEqual(alerts[0].severity, AlertSeverity.CRITICAL)

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_incident_severity_low(self, mock_get):
        incident = _make_rootly_incident(severity="low")
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [incident],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider()
        alerts = provider._pull_incidents()
        self.assertEqual(alerts[0].severity, AlertSeverity.LOW)

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_incident_status_mapping(self, mock_get):
        started = _make_rootly_incident(incident_id="i1", status="started")
        triage = _make_rootly_incident(incident_id="i2", status="in_triage")
        mitigated = _make_rootly_incident(incident_id="i3", status="mitigated")
        closed = _make_rootly_incident(incident_id="i4", status="closed")

        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [started, triage, mitigated, closed],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider()
        alerts = provider._pull_incidents()
        self.assertEqual(alerts[0].status, AlertStatus.FIRING)
        self.assertEqual(alerts[1].status, AlertStatus.ACKNOWLEDGED)
        self.assertEqual(alerts[2].status, AlertStatus.PENDING)
        self.assertEqual(alerts[3].status, AlertStatus.RESOLVED)

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_incident_service_extraction(self, mock_get):
        incident = _make_rootly_incident(
            services=[
                {"data": {"attributes": {"name": "web-app"}}},
                {"data": {"attributes": {"name": "api"}}},
            ]
        )
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [incident],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider()
        alerts = provider._pull_incidents()
        self.assertIn("web-app", alerts[0].service)
        self.assertIn("api", alerts[0].service)

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_incident_slack_channel(self, mock_get):
        incident = _make_rootly_incident()
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [incident],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider()
        alerts = provider._pull_incidents()
        self.assertEqual(alerts[0].labels["slack_channel"], "inc-database-outage")

    @patch("keep.providers.rootly_provider.rootly_provider.requests.get")
    def test_incident_fingerprint(self, mock_get):
        incident = _make_rootly_incident(incident_id="xyz-789")
        mock_get.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={
                "data": [incident],
                "meta": {"next_page": None},
            }),
        )

        provider = _create_provider()
        alerts = provider._pull_incidents()
        self.assertEqual(alerts[0].fingerprint, "rootly-incident-xyz-789")


class TestWebhookFormatting(unittest.TestCase):
    """Test webhook event formatting."""

    def test_format_alert_created(self):
        event = {
            "type": "alert.created",
            "data": _make_rootly_alert(),
        }
        alert = RootlyProvider._format_alert(event)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_alert_resolved(self):
        event = {
            "type": "alert.resolved",
            "data": _make_rootly_alert(status="resolved"),
        }
        alert = RootlyProvider._format_alert(event)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_format_incident_created(self):
        event = {
            "type": "incident.created",
            "data": _make_rootly_incident(),
        }
        alert = RootlyProvider._format_alert(event)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_incident_mitigated(self):
        event = {
            "type": "incident.mitigated",
            "data": _make_rootly_incident(status="mitigated"),
        }
        alert = RootlyProvider._format_alert(event)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.status, AlertStatus.PENDING)

    def test_format_incident_resolved(self):
        event = {
            "type": "incident.resolved",
            "data": _make_rootly_incident(status="resolved"),
        }
        alert = RootlyProvider._format_alert(event)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_format_incident_cancelled(self):
        event = {
            "type": "incident.cancelled",
            "data": _make_rootly_incident(status="cancelled"),
        }
        alert = RootlyProvider._format_alert(event)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.status, AlertStatus.SUPPRESSED)

    def test_format_batch_events(self):
        events = [
            {"type": "alert.created", "data": _make_rootly_alert(alert_id="a1")},
            {"type": "incident.created", "data": _make_rootly_incident(incident_id="i1")},
        ]
        alerts = RootlyProvider._format_alert(events)
        self.assertIsNotNone(alerts)
        self.assertEqual(len(alerts), 2)

    def test_format_incident_severity_from_webhook(self):
        event = {
            "type": "incident.created",
            "data": _make_rootly_incident(severity="high"),
        }
        alert = RootlyProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.HIGH)


class TestSeverityMapping(unittest.TestCase):
    """Test severity and status mappings."""

    def test_severity_map(self):
        expected = {
            "critical": AlertSeverity.CRITICAL,
            "high": AlertSeverity.HIGH,
            "major": AlertSeverity.HIGH,
            "medium": AlertSeverity.WARNING,
            "warning": AlertSeverity.WARNING,
            "low": AlertSeverity.LOW,
            "minor": AlertSeverity.LOW,
            "info": AlertSeverity.INFO,
        }
        for name, severity in expected.items():
            self.assertEqual(
                RootlyProvider.SEVERITIES_MAP[name],
                severity,
                f"Severity mismatch for '{name}'",
            )

    def test_status_map_alerts(self):
        self.assertEqual(RootlyProvider.STATUS_MAP["open"], AlertStatus.FIRING)
        self.assertEqual(RootlyProvider.STATUS_MAP["acknowledged"], AlertStatus.ACKNOWLEDGED)
        self.assertEqual(RootlyProvider.STATUS_MAP["resolved"], AlertStatus.RESOLVED)
        self.assertEqual(RootlyProvider.STATUS_MAP["noise"], AlertStatus.SUPPRESSED)

    def test_status_map_incidents(self):
        self.assertEqual(RootlyProvider.STATUS_MAP["started"], AlertStatus.FIRING)
        self.assertEqual(RootlyProvider.STATUS_MAP["in_triage"], AlertStatus.ACKNOWLEDGED)
        self.assertEqual(RootlyProvider.STATUS_MAP["mitigated"], AlertStatus.PENDING)
        self.assertEqual(RootlyProvider.STATUS_MAP["closed"], AlertStatus.RESOLVED)
        self.assertEqual(RootlyProvider.STATUS_MAP["cancelled"], AlertStatus.SUPPRESSED)


class TestSimulateAlert(unittest.TestCase):
    """Test alert simulation."""

    def test_simulate_returns_valid_event(self):
        event = RootlyProvider.simulate_alert()
        self.assertIn("type", event)
        self.assertIn("data", event)

    def test_simulated_event_can_be_formatted(self):
        event = RootlyProvider.simulate_alert()
        alert = RootlyProvider._format_alert(event)
        self.assertIsNotNone(alert)
        self.assertIn("rootly", alert.source)

    def test_simulate_produces_alert_or_incident(self):
        # Run multiple times to cover both paths
        types_seen = set()
        for _ in range(50):
            event = RootlyProvider.simulate_alert()
            event_type = event["type"]
            if "alert" in event_type:
                types_seen.add("alert")
            elif "incident" in event_type:
                types_seen.add("incident")

        # Should see both types over 50 iterations
        self.assertIn("alert", types_seen)
        self.assertIn("incident", types_seen)


class TestResolveAlertSeverity(unittest.TestCase):
    """Test severity inference from labels."""

    def test_severity_from_labels(self):
        provider = _create_provider()
        attrs = {
            "labels": [{"key": "severity", "value": "high"}],
        }
        severity = provider._resolve_alert_severity(attrs)
        self.assertEqual(severity, AlertSeverity.HIGH)

    def test_severity_from_priority_label(self):
        provider = _create_provider()
        attrs = {
            "labels": [{"key": "priority", "value": "critical"}],
        }
        severity = provider._resolve_alert_severity(attrs)
        self.assertEqual(severity, AlertSeverity.CRITICAL)

    def test_severity_default_warning(self):
        provider = _create_provider()
        attrs = {"labels": []}
        severity = provider._resolve_alert_severity(attrs)
        self.assertEqual(severity, AlertSeverity.WARNING)


if __name__ == "__main__":
    unittest.main()
