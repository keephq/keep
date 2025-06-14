"""Unit tests for the Falco provider."""

import hashlib
import sys
import types
import unittest


# Provide a very small stub for BaseProvider so the Falco provider can be
# imported without pulling in the entire application dependencies.
stub_base_provider = types.ModuleType("keep.providers.base.base_provider")


class StubBaseProvider:
    """Lightweight stand-in for BaseProvider used in tests."""

    @staticmethod
    def get_alert_fingerprint(alert, fingerprint_fields=None):
        if not fingerprint_fields:
            return alert.name
        fingerprint = hashlib.sha256()
        event_dict = alert.dict()
        for field in fingerprint_fields:
            value = event_dict.get(field)
            if value is not None:
                fingerprint.update(str(value).encode())
        return fingerprint.hexdigest()


stub_base_provider.BaseProvider = StubBaseProvider
sys.modules["keep.providers.base.base_provider"] = stub_base_provider

# Stub ProviderConfig to avoid heavy dependencies like `chevron` during import
stub_provider_config = types.ModuleType("keep.providers.models.provider_config")


class StubProviderConfig:
    """Minimal stand-in for ProviderConfig used in tests."""

    def __init__(self, *args, **kwargs):
        pass


stub_provider_config.ProviderConfig = StubProviderConfig
sys.modules["keep.providers.models.provider_config"] = stub_provider_config

from keep.providers.falco_provider.falco_provider import FalcoProvider


class TestFalcoProvider(unittest.TestCase):
    def test_format_alert(self):
        provider = None
        event = {
            "rule": "Terminal shell in container",
            "output": "A shell was spawned in a container",
            "priority": "Notice",
            "time": "2024-01-01T00:00:00Z",
            "hostname": "k8s-node",
        }
        alert = FalcoProvider._format_alert(event, provider)

        self.assertEqual(alert.name, "Terminal shell in container")
        self.assertEqual(alert.description, "A shell was spawned in a container")
        # AlertDto converts enums to their values, so severity and status are strings
        self.assertEqual(alert.severity, "info")
        self.assertEqual(alert.status, "firing")
        self.assertTrue(alert.lastReceived.startswith("2024-01-01T00:00:00"))
        self.assertEqual(alert.environment, "k8s-node")
        self.assertEqual(alert.source, ["falco"])


if __name__ == "__main__":
    unittest.main()
