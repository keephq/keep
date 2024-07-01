import unittest
import json
from datetime import datetime
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.pagerduty_provider.pagerduty_provider import PagerdutyProvider
import os

class TestPagerdutyProvider(unittest.TestCase):

    def setUp(self):
        self.sample_data_path = 'sample_incident_data.json'
        if not os.path.exists(self.sample_data_path):
            sample_data = {
                "id": "Q03JN8CB34CWDG",
                "incident_number": 1,
                "title": "Past incident",
                "description": "Past incident",
                "status": "triggered",
                "urgency": "high",
                "created_at": "2024-06-23T08:59:05Z",
                "service": {
                    "summary": "Default Service",
                    "id": "PZ8ZXYP",
                    "type": "service_reference"
                },
                "escalation_policy": {
                    "id": "PA3HPIW",
                    "type": "escalation_policy_reference",
                    "summary": "Default"
                },
                "assignments": [
                    {
                        "assignee": {
                            "id": "PMTYMKM",
                            "type": "user_reference",
                            "summary": "M K"
                        }
                    }
                ],
                "first_trigger_log_entry": {
                    "id": "R4E9AV53IQZLQY",
                    "type": "trigger_log_entry_reference",
                    "summary": "Triggered through the website.",
                    "self": "https://api.pagerduty.com/log_entries/R4E9AV53IQZLQY",
                    "html_url": "https://keephqasdkjbkvhjsadvglk.pagerduty.com/incidents/Q03JN8CB34CWDG/log_entries/R4E9AV53IQZLQY"
                },
                "html_url": "https://keephqasdkjbkvhjsadvglk.pagerduty.com/incidents/Q03JN8CB34CWDG"
            }
            with open(self.sample_data_path, 'w') as f:
                json.dump(sample_data, f)

    def test_format_alert(self):
        with open(self.sample_data_path, 'r') as f:
            sample_data = json.load(f)

        formatted_alert = PagerdutyProvider._format_alert({"event": {"data": sample_data}})

        self.assertIsInstance(formatted_alert, AlertDto)
        self.assertEqual(formatted_alert.name, "Past incident")
        self.assertEqual(formatted_alert.description, "Past incident")
        self.assertEqual(formatted_alert.status, AlertStatus.FIRING.value)
        self.assertEqual(formatted_alert.severity, AlertSeverity.INFO.value)
        self.assertEqual(formatted_alert.source, ["pagerduty"])
        # Check the labels for additional metadata
        labels = formatted_alert.labels
        self.assertEqual(labels.get("incident_number"), 1)
        self.assertEqual(labels.get("urgency"), "high")
        self.assertEqual(labels.get("escalation_policy"), "Default")
        self.assertEqual(labels.get("teams"), [])
        self.assertEqual(len(labels.get("assignments", [])), 1)
        self.assertEqual(labels.get("assignments")[0].get("assignee"), "M K")
        self.assertEqual(labels.get("impacted_services"), ["Default Service"])
        self.assertEqual(labels.get("acknowledgers"), [])
        self.assertEqual(labels.get("first_trigger_log_entry"), "Triggered through the website.")
        self.assertIsNone(labels.get("conference_bridge"))
    def tearDown(self):
        if os.path.exists(self.sample_data_path):
            os.remove(self.sample_data_path)

if __name__ == '__main__':
    unittest.main()