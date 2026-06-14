import json
import os
import unittest
from unittest.mock import MagicMock

from keep.api.models.db.incident import IncidentSeverity, IncidentStatus
from keep.providers.pagerduty_provider.pagerduty_provider import PagerdutyProvider


class TestPagerdutyProvider(unittest.TestCase):
    def test_format_alert(self):
        with open(os.path.join(os.path.dirname(__file__), "test.json"), "r") as f:
            data = json.load(f)

        formatted_alert = PagerdutyProvider._format_incident({"event": {"data": data}})

        self.assertEqual(formatted_alert.name, "PD-Fifth Alert-Q11LATZGWTP02U")
        self.assertEqual(formatted_alert.severity, IncidentSeverity.HIGH)
        self.assertEqual(formatted_alert.status, IncidentStatus.FIRING)
        self.assertEqual(formatted_alert.alert_sources, ["pagerduty"])

    def _make_provider(self):
        """Create a minimal PagerdutyProvider for unit testing _build_alert."""
        ctx = MagicMock()
        ctx.event_context = None
        config = MagicMock()
        config.authentication = {"routing_key": "test-key"}
        provider = object.__new__(PagerdutyProvider)
        provider.context_manager = ctx
        provider.logger = MagicMock()
        return provider

    def test_build_alert_includes_client_fields(self):
        provider = self._make_provider()
        payload = provider._build_alert(
            title="Test alert",
            routing_key="test-routing-key",
            client="My Monitoring Tool",
            client_url="https://monitoring.example.com",
        )
        self.assertEqual(payload["client"], "My Monitoring Tool")
        self.assertEqual(payload["client_url"], "https://monitoring.example.com")
        # client and client_url should be top-level, not inside payload.payload
        self.assertNotIn("client", payload["payload"])
        self.assertNotIn("client_url", payload["payload"])

    def test_build_alert_omits_client_fields_when_not_provided(self):
        provider = self._make_provider()
        payload = provider._build_alert(
            title="Test alert",
            routing_key="test-routing-key",
        )
        self.assertNotIn("client", payload)
        self.assertNotIn("client_url", payload)

    def test_build_alert_images_and_links_in_payload(self):
        provider = self._make_provider()
        payload = provider._build_alert(
            title="Test alert",
            routing_key="test-routing-key",
            images=[{"src": "https://example.com/img.png"}],
            links=[{"href": "https://example.com", "text": "Example"}],
        )
        self.assertIn("images", payload["payload"])
        self.assertIn("links", payload["payload"])


if __name__ == "__main__":
    unittest.main()
