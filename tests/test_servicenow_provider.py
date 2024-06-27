import unittest
from keep.providers.servicenow_provider import ServicenowProvider

class TestServiceNowProvider(unittest.TestCase):
    def setUp(self):
        self.provider = ServicenowProvider('instance', 'user', 'password')

    def test_fetch_incidents(self):
        incidents = self.provider.fetch_incidents()
        self.assertIsInstance(incidents, list)

    def test_transform_incidents(self):
        incidents = [{'sys_id': '1', 'short_description': 'Test', 'state': 'New', 'priority': '1', 'assigned_to': 'User', 'opened_at': '2023-06-26', 'resolved_at': '2023-06-27'}]
        transformed = self.provider.transform_incidents(incidents)
        self.assertEqual(len(transformed), 1)
        self.assertIn('id', transformed[0])

    def test_fetch_and_ingest_incidents(self):
        # Mock the fetch_incidents method to return test data
        self.provider.fetch_incidents = lambda: [{'sys_id': '1', 'short_description': 'Test', 'state': 'New', 'priority': '1', 'assigned_to': 'User', 'opened_at': '2023-06-26', 'resolved_at': '2023-06-27'}]
        self.provider.ingest_into_keep = lambda events: self.assertEqual(len(events), 1)
        self.provider.fetch_and_ingest_incidents()

if __name__ == '__main__':
    unittest.main()
