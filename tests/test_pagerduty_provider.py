import unittest
import json
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.pagerduty_provider.pagerduty_provider import PagerdutyProvider
import os


class TestPagerdutyProvider(unittest.TestCase):
    def test_format_alert(self):
        with open(os.path.join(os.path.dirname(__file__), "test.json"), "r") as f:
            data = json.load(f)

        formatted_alert = PagerdutyProvider._format_alert({"event": {"data": data}})

        self.assertEqual(formatted_alert.name, "Fifth Alert")
        self.assertEqual(formatted_alert.severity, AlertSeverity.WARNING.value)
        self.assertEqual(formatted_alert.status, AlertStatus.FIRING.value)
        self.assertEqual(formatted_alert.source, ["pagerduty"])

        labels = formatted_alert.labels
        self.assertEqual(labels.get("urgency"), "high")
        self.assertEqual(labels.get("acknowledgers"), [])
        self.assertEqual(labels.get("last_updated_by"), "Default Service")
        self.assertEqual(labels.get("conference_bridge"), None)
        self.assertEqual(labels.get("impacted_services"), "Default Service")


if __name__ == "__main__":
    unittest.main()
        