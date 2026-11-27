import unittest
from datetime import datetime
from keep.api.alert_deduplicator.alert_deduplicator import AlertDeduplicator
from keep.api.models.alert import AlertDto


class TestAlertDeduplicatorRemoveField(unittest.TestCase):
    def setUp(self):
        self.deduplicator = AlertDeduplicator(tenant_id="test-tenant")

    def test_remove_existing_nested_field(self):
        alert = AlertDto(
            id="test-1",
            name="test-alert",
            status="firing",
            lastReceived=str(datetime.now()),
            source=["keep"],
            labels={"pod": "my-pod", "namespace": "prod"},
        )
        cleaned = self.deduplicator._remove_field("labels.pod", alert)
        self.assertNotIn("pod", cleaned.labels)
        self.assertEqual(cleaned.labels.get("namespace"), "prod")
        # Ensure original alert is unchanged (deep copy)
        self.assertIn("pod", alert.labels)

    def test_remove_missing_nested_field_does_not_raise(self):
        """Fix for issue #6849: alert lacking nested field should not raise KeyError or drop alert."""
        alert = AlertDto(
            id="test-2",
            name="test-alert",
            status="firing",
            lastReceived=str(datetime.now()),
            source=["keep"],
            labels={"namespace": "prod"},  # missing 'pod'
        )
        cleaned = self.deduplicator._remove_field("labels.pod", alert)
        self.assertEqual(cleaned.labels, {"namespace": "prod"})

    def test_remove_nested_field_when_intermediate_missing(self):
        alert = AlertDto(
            id="test-3",
            name="test-alert",
            status="firing",
            lastReceived=str(datetime.now()),
            source=["keep"],
            labels={"namespace": "prod"},
        )
        cleaned = self.deduplicator._remove_field("labels.sub.pod", alert)
        self.assertEqual(cleaned.labels, {"namespace": "prod"})

    def test_remove_nested_field_when_root_attr_is_none_or_not_dict(self):
        alert = AlertDto(
            id="test-4",
            name="test-alert",
            status="firing",
            lastReceived=str(datetime.now()),
            source=["keep"],
            labels={},
        )
        # Testing with non-dict attribute
        cleaned = self.deduplicator._remove_field("status.nested", alert)
        self.assertEqual(cleaned.status, "firing")

    def test_remove_top_level_field(self):
        alert = AlertDto(
            id="test-5",
            name="test-alert",
            status="firing",
            lastReceived=str(datetime.now()),
            source=["keep"],
            description="some description",
        )
        cleaned = self.deduplicator._remove_field("description", alert)
        self.assertFalse(hasattr(cleaned, "description"))


if __name__ == "__main__":
    unittest.main()
