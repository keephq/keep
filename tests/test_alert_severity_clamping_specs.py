import unittest

class TestAlertSeverityClamping(unittest.TestCase):
    def test_severity_level_mapping_valid(self):
        valid_severities = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
        incoming = "HIGH".lower()
        
        self.assertIn(incoming, valid_severities)
        self.assertEqual(valid_severities[incoming], 3)

    def test_unknown_severity_fallback_to_info(self):
        valid_severities = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
        incoming_unknown = "unspecified_level"
        
        resolved = valid_severities.get(incoming_unknown, valid_severities["info"])
        self.assertEqual(resolved, 0)

if __name__ == "__main__":
    unittest.main()
