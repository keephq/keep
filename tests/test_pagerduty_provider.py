import json
import os
import unittest

from keep.api.models.db.incident import IncidentSeverity, IncidentStatus
from keep.providers.pagerduty_provider.pagerduty_provider import PagerdutyProvider


class TestPagerdutyProvider(unittest.TestCase):
    def test_format_alert(self):
        with open(os.path.join(os.path.dirname(__file__), "test.json"), "r") as f:
            data = json.load(f)

        formatted_alert = PagerdutyProvider._format_incident({"event": {"data": data}})

        self.assertEqual(formatted_alert.name, "PD-Fifth Alert-Q11LATZGWTP02U")
        self.assertEqual(formatted_alert.severity, IncidentSeverity.WARNING)
        self.assertEqual(formatted_alert.status, IncidentStatus.FIRING)
        self.assertEqual(formatted_alert.alert_sources, ["pagerduty"])


if __name__ == "__main__":
    unittest.main()
