import unittest
from unittest.mock import MagicMock
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.api.models.alert import AlertSeverity
from keep.providers.models.provider_config import ProviderConfig


class TestSnmpProvider(unittest.TestCase):
    def setUp(self):
        # 1. Mock the Context Manager (Keep's engine)
        self.mock_context = MagicMock()

        # 2. Setup the Config properly
        # We define id and name because BaseProvider metadata often requires them
        config_obj = ProviderConfig(
            id="snmp-test-config",
            name="snmp-test-provider",
            authentication={
                "port": 162,
                "community": "public",
                "denoise_window": 5
            }
        )

        # 3. Initialize
        self.provider = SnmpProvider(
            context_manager=self.mock_context,
            provider_id="snmp-test",
            config=config_obj
        )
        # Mock the logger to prevent console noise during tests
        self.provider.logger = MagicMock()

    def test_denoising_logic(self):
        """Proof of the Signal Denoising Edge: Rapid traps must be dropped."""
        mock_engine = MagicMock()
        # Mock Source IP: 1.2.3.4
        mock_engine.msgAndPduDsp.getTransportInfo.return_value = (None, ("1.2.3.4", 162))

        # Simulated 'linkDown' Trap
        var_binds = [
            ("1.3.6.1.2.1.1.3.0", 100),
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")
        ]

        # 1. First attempt: Should push event to the event manager
        self.provider._process_trap(mock_engine, None, None, None, var_binds, None)
        self.provider.context_manager.event_manager.push_event.assert_called_once()

        # Reset the mock for the second attempt
        self.provider.context_manager.event_manager.push_event.reset_mock()

        # 2. Second attempt (immediate): Should be BLOCKED by denoising logic
        self.provider._process_trap(mock_engine, None, None, None, var_binds, None)
        self.provider.context_manager.event_manager.push_event.assert_not_called()

    def test_severity_mapping(self):
        """Verify the OID to Severity mapping works correctly."""
        mock_engine = MagicMock()
        mock_engine.msgAndPduDsp.getTransportInfo.return_value = (None, ("10.0.0.1", 162))

        # LinkDown OID
        var_binds = [
            ("1.3.6.1.2.1.1.3.0", 100),
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.6.3.1.1.5.3")
        ]

        self.provider._process_trap(mock_engine, None, None, None, var_binds, None)

        # Capture the alert
        pushed_alert = self.mock_context.event_manager.push_event.call_args[0][0]

        # --- THE BULLETPROOF FIX: Compare as strings ---
        # We use str() on both to ensure we're comparing 'critical' == 'critical'
        severity_value = pushed_alert.severity.value if hasattr(pushed_alert.severity,
                                                                'value') else pushed_alert.severity
        expected_value = AlertSeverity.CRITICAL.value if hasattr(AlertSeverity.CRITICAL,
                                                                 'value') else AlertSeverity.CRITICAL

        self.assertEqual(str(severity_value), str(expected_value))
        self.assertEqual(pushed_alert.service, "10.0.0.1")

if __name__ == "__main__":
    unittest.main()