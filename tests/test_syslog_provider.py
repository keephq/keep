"""Tests for SyslogProvider."""

import asyncio
import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Add the repo root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from keep.providers.syslog_provider.syslog_provider import (
    SyslogProvider,
    SyslogProviderAuthConfig,
    SYSLOG_SEVERITY_MAP,
    SYSLOG_SEVERITY_NAMES,
    SYSLOG_FACILITY_NAMES,
)


class TestSyslogParsing(unittest.TestCase):
    """Test syslog message parsing."""

    def setUp(self):
        """Set up a mock provider instance for parsing tests."""
        self.mock_context = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.authentication = {"host": "0.0.0.0", "port": 514}
        self.provider = SyslogProvider.__new__(SyslogProvider)
        self.provider.logger = MagicMock()
        self.provider.authentication_config = SyslogProviderAuthConfig(
            **self.mock_config.authentication
        )

    def test_parse_priority(self):
        """Test priority parsing into facility and severity."""
        # priority = facility * 8 + severity
        # kern.emergency = 0*8+0 = 0
        facility, severity, fac_name, sev_name = SyslogProvider._parse_priority(0)
        self.assertEqual(facility, 0)
        self.assertEqual(severity, 0)
        self.assertEqual(fac_name, "kern")
        self.assertEqual(sev_name, "emergency")

        # user.error = 1*8+3 = 11
        facility, severity, fac_name, sev_name = SyslogProvider._parse_priority(11)
        self.assertEqual(facility, 1)
        self.assertEqual(severity, 3)
        self.assertEqual(fac_name, "user")
        self.assertEqual(sev_name, "error")

        # local7.debug = 23*8+7 = 191
        facility, severity, fac_name, sev_name = SyslogProvider._parse_priority(191)
        self.assertEqual(facility, 23)
        self.assertEqual(severity, 7)
        self.assertEqual(fac_name, "local7")
        self.assertEqual(sev_name, "debug")

    def test_map_severity(self):
        """Test syslog severity to Keep alert severity mapping."""
        self.assertEqual(SyslogProvider._map_severity(0), "critical")  # Emergency
        self.assertEqual(SyslogProvider._map_severity(1), "critical")  # Alert
        self.assertEqual(SyslogProvider._map_severity(2), "critical")  # Critical
        self.assertEqual(SyslogProvider._map_severity(3), "high")     # Error
        self.assertEqual(SyslogProvider._map_severity(4), "warning")  # Warning
        self.assertEqual(SyslogProvider._map_severity(5), "info")     # Notice
        self.assertEqual(SyslogProvider._map_severity(6), "info")     # Informational
        self.assertEqual(SyslogProvider._map_severity(7), "low")      # Debug

    def test_parse_rfc3164(self):
        """Test RFC 3164 (BSD) syslog message parsing."""
        # <34>Jan 11 22:14:15 myhost sshd[1234]: Failed password for root
        result = self.provider._parse_syslog_message(
            "<34>Jan 11 22:14:15 myhost sshd[1234]: Failed password for root"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["syslog_hostname"], "myhost")
        self.assertEqual(result["syslog_app_name"], "sshd")
        self.assertEqual(result["syslog_pid"], "1234")
        self.assertEqual(result["message"], "Failed password for root")
        self.assertEqual(result["severity"], "critical")  # priority 34 = 4*8+2 = auth.critical
        self.assertEqual(result["source"], "syslog")

    def test_parse_rfc3164_no_pid(self):
        """Test RFC 3164 message without PID."""
        result = self.provider._parse_syslog_message(
            "<13>Jan 11 22:14:15 myhost kernel: Out of memory"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["syslog_hostname"], "myhost")
        self.assertEqual(result["syslog_app_name"], "kernel")
        self.assertEqual(result["message"], "Out of memory")

    def test_parse_rfc5424(self):
        """Test RFC 5424 syslog message parsing."""
        # <34>1 2024-01-11T22:14:15.003Z myhost sshd 1234 - - Failed password for root
        result = self.provider._parse_syslog_message(
            "<34>1 2024-01-11T22:14:15.003Z myhost sshd 1234 - - Failed password for root"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["syslog_hostname"], "myhost")
        self.assertEqual(result["syslog_app_name"], "sshd")
        self.assertEqual(result["syslog_pid"], "1234")
        self.assertEqual(result["message"], "Failed password for root")
        self.assertEqual(result["severity"], "high")

    def test_parse_malformed_fallback(self):
        """Test fallback for malformed messages."""
        # Message with priority but non-standard format
        result = self.provider._parse_syslog_message(
            "<133>Some random message without standard format"
        )
        self.assertIsNotNone(result)
        self.assertIn("syslog", result["source"])
        self.assertIn("Some random message", result["message"])

    def test_parse_empty_message(self):
        """Test empty message returns None."""
        result = self.provider._parse_syslog_message("")
        self.assertIsNone(result)

        result = self.provider._parse_syslog_message("   ")
        self.assertIsNone(result)

    def test_parse_no_priority(self):
        """Test message without priority gets default informational."""
        result = self.provider._parse_syslog_message("just a plain message")
        self.assertIsNotNone(result)
        self.assertEqual(result["severity"], "info")  # default to informational


class TestSyslogProviderConfig(unittest.TestCase):
    """Test provider configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SyslogProviderAuthConfig()
        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 514)

    def test_custom_config(self):
        """Test custom configuration values."""
        config = SyslogProviderAuthConfig(host="127.0.0.1", port=1514)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 1514)


class TestSyslogTCPServer(unittest.TestCase):
    """Test TCP server functionality."""

    def setUp(self):
        self.mock_context = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.authentication = {"host": "127.0.0.1", "port": 1514}
        self.provider = SyslogProvider.__new__(SyslogProvider)
        self.provider.logger = MagicMock()
        self.provider.authentication_config = SyslogProviderAuthConfig(
            **self.mock_config.authentication
        )
        self.provider.consume = True
        self.provider._push_alert = MagicMock()

    def test_handle_connection_pushes_alerts(self):
        """Test that received syslog messages are parsed and pushed as alerts."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Simulate a connection that sends a syslog message
            reader = asyncio.StreamReader()
            reader.feed_data(b"<34>Jan 11 22:14:15 myhost sshd[1234]: Test message\n")
            reader.feed_eof()

            writer = MagicMock()
            writer.get_extra_info.return_value = ("127.0.0.1", 12345)
            writer.close = MagicMock()
            writer.wait_closed = AsyncMock()

            loop.run_until_complete(
                self.provider._handle_connection(reader, writer)
            )

            self.provider._push_alert.assert_called_once()
            alert = self.provider._push_alert.call_args[0][0]
            self.assertEqual(alert["syslog_hostname"], "myhost")
            self.assertEqual(alert["message"], "Test message")
        finally:
            loop.close()

    def test_handle_connection_multiple_messages(self):
        """Test multiple messages in a single connection."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            reader = asyncio.StreamReader()
            reader.feed_data(
                b"<34>Jan 11 22:14:15 host1 app1[1]: msg1\n"
                b"<13>Jan 11 22:14:16 host2 app2[2]: msg2\n"
            )
            reader.feed_eof()

            writer = MagicMock()
            writer.get_extra_info.return_value = ("127.0.0.1", 12345)
            writer.close = MagicMock()
            writer.wait_closed = AsyncMock()

            loop.run_until_complete(
                self.provider._handle_connection(reader, writer)
            )

            self.assertEqual(self.provider._push_alert.call_count, 2)
        finally:
            loop.close()

    def test_stop_consume(self):
        """Test stop_consume sets flag and closes server."""
        self.provider._server = MagicMock()
        self.provider._loop = None
        self.provider.stop_consume()
        self.assertFalse(self.provider.consume)
        self.provider._server.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
