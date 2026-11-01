"""Pure parser tests; unittest bypasses the service-level pytest fixtures."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "tag_parser", ROOT / "keep/providers/site24x7_provider/tag_parser.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
parse_tags = module.parse_tags


class TagParserTests(unittest.TestCase):
    def test_key_value_pairs(self):
        self.assertEqual(parse_tags("env:prod,team:backend"), {"env": "prod", "team": "backend"})

    def test_plain_tags(self):
        self.assertEqual(parse_tags("critical, env:prod"), {"critical": "critical", "env": "prod"})

    def test_colons_in_values(self):
        self.assertEqual(parse_tags("url:https://example.com:443"), {"url": "https://example.com:443"})

    def test_whitespace(self):
        self.assertEqual(parse_tags(" env : prod , team : backend "), {"env": "prod", "team": "backend"})

    def test_empty_keys_and_separators(self):
        self.assertEqual(parse_tags(",,:bad, :bad,env:prod,,"), {"env": "prod"})

    def test_empty_value_is_retained(self):
        self.assertEqual(parse_tags("env:"), {"env": ""})

    def test_duplicate_keys_last_value_wins(self):
        self.assertEqual(parse_tags("env:dev,env:prod"), {"env": "prod"})

    def test_missing_or_unsupported_types(self):
        for raw in (None, "", 42, [], True):
            with self.subTest(raw=raw):
                self.assertEqual(parse_tags(raw), {})

    def test_mapping_is_copied(self):
        original = {"env": "prod"}
        labels = parse_tags(original)
        labels["env"] = "dev"
        self.assertEqual(original, {"env": "prod"})

    def test_mapping_empty_key(self):
        self.assertEqual(parse_tags({"": "invalid", "env": "prod"}), {"env": "prod"})
