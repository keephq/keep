import unittest
from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.keep_provider.keep_provider import KeepProvider
from keep.providers.models.provider_config import ProviderConfig


class TestTernaryExpressions(unittest.TestCase):
    """Test cases for the _handle_ternary_expressions method."""

    def setUp(self):
        """Set up a KeepProvider instance with mocked dependencies for testing."""
        self.context_manager = ContextManager(
            tenant_id="test", workflow_id="test-workflow"
        )

        self.config = MagicMock(spec=ProviderConfig)

        self.provider = KeepProvider(
            context_manager=self.context_manager,
            provider_id="test-provider",
            config=self.config,
        )

        # Mock logger to capture log messages
        self.provider.logger = MagicMock()

    def test_simple_ternary_true_condition(self):
        """Test a simple ternary expression with a true condition."""
        params = {"severity": "10 > 5 ? 'critical' : 'info'"}
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result["severity"], "critical")

    def test_simple_ternary_false_condition(self):
        """Test a simple ternary expression with a false condition."""
        params = {"severity": "10 < 5 ? 'critical' : 'info'"}
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result["severity"], "info")

    def test_nested_ternary(self):
        """Test a nested ternary expression."""
        params = {"severity": "10 > 9 ? 'critical' : 10 > 7 ? 'warning' : 'info'"}
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result["severity"], "critical")

    def test_nested_ternary_multiple_levels(self):
        """Test a nested ternary expression with multiple levels."""
        params = {
            "severity": "0.95 > 0.9 ? 'critical' : 0.8 > 0.7 ? 'warning' : 0.6 > 0.5 ? 'notice' : 'info'"
        }
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result["severity"], "critical")

        params = {
            "severity": "0.85 > 0.9 ? 'critical' : 0.8 > 0.7 ? 'warning' : 0.6 > 0.5 ? 'notice' : 'info'"
        }
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result["severity"], "warning")

        params = {
            "severity": "0.85 > 0.9 ? 'critical' : 0.6 > 0.7 ? 'warning' : 0.6 > 0.5 ? 'notice' : 'info'"
        }
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result["severity"], "notice")

        params = {
            "severity": "0.85 > 0.9 ? 'critical' : 0.6 > 0.7 ? 'warning' : 0.4 > 0.5 ? 'notice' : 'info'"
        }
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result["severity"], "info")

    def test_non_ternary_expressions_unchanged(self):
        """Test that non-ternary expressions are left unchanged."""
        params = {
            "name": "Test Alert",
            "count": "5",
            "message": "System error occurred",
            "query": "SELECT * FROM table WHERE value > 100",
        }
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result, params)

    def test_real_world_example(self):
        """Test with the real-world example from the original code."""
        params = {
            "severity": "0.012899999999999995 > 0.9 ? 'critical' : 0.012899999999999995 > 0.7 ? 'warning' : 'info'"
        }
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result["severity"], "info")

    def test_error_during_evaluation(self):
        """Test handling of errors during evaluation."""
        params = {"level": "undefined_var > 10 ? 'high' : 'low'"}

        with patch("asteval.Interpreter") as mock_interpreter:
            mock_aeval = MagicMock()
            mock_interpreter.return_value = mock_aeval
            mock_aeval.error_msg = "NameError: name 'undefined_var' is not defined"

            # Make evaluation return None to simulate an error
            mock_aeval.return_value = None

            result = self.provider._handle_ternary_expressions(params)

            # Original value should be preserved on error
            self.assertEqual(result["level"], "undefined_var > 10 ? 'high' : 'low'")

            # A warning should be logged
            self.provider.logger.warning.assert_called()

    def test_non_string_values(self):
        """Test that non-string values are left unchanged."""
        params = {
            "count": 5,
            "enabled": True,
            "factors": [1, 2, 3],
            "mapping": {"key": "value"},
        }
        result = self.provider._handle_ternary_expressions(params)
        self.assertEqual(result, params)

    def test_exception_handling(self):
        """Test that exceptions are handled gracefully."""
        params = {"severity": "10 > 5 ? 'critical' : 'info'"}

        with patch("asteval.Interpreter") as mock_interpreter:
            # Make the interpreter raise an exception
            mock_interpreter.side_effect = Exception("Test exception")

            result = self.provider._handle_ternary_expressions(params)

            # Original value should be preserved
            self.assertEqual(result["severity"], "10 > 5 ? 'critical' : 'info'")

            # A warning should be logged
            self.provider.logger.warning.assert_called()


if __name__ == "__main__":
    unittest.main()
