"""
SyslogProvider is a class that provides a way to ingest syslog messages received on a TCP port.
"""

import asyncio
import dataclasses
import re
import typing
import uuid

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


SYSLOG_SEVERITY_MAP = {
    0: "critical",   # Emergency
    1: "critical",   # Alert
    2: "critical",   # Critical
    3: "high",       # Error
    4: "warning",    # Warning
    5: "info",       # Notice
    6: "info",       # Informational
    7: "low",        # Debug
}

SYSLOG_SEVERITY_NAMES = {
    0: "emergency",
    1: "alert",
    2: "critical",
    3: "error",
    4: "warning",
    5: "notice",
    6: "informational",
    7: "debug",
}

SYSLOG_FACILITY_NAMES = {
    0: "kern", 1: "user", 2: "mail", 3: "daemon",
    4: "auth", 5: "syslog", 6: "lpr", 7: "news",
    8: "uucp", 9: "cron", 10: "authpriv", 11: "ftp",
    12: "ntp", 13: "security", 14: "console", 15: "solaris-cron",
    16: "local0", 17: "local1", 18: "local2", 19: "local3",
    20: "local4", 21: "local5", 22: "local6", 23: "local7",
}

# RFC 3164: <priority>timestamp hostname app-name[pid]: message
RFC3164_RE = re.compile(
    r"^<(\d+)>"                          # priority
    r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"  # timestamp (BSD)
    r"(\S+)\s+"                           # hostname
    r"(\S+?)(?:\[(\d+)\])?:\s*"          # app-name[pid]:
    r"(.*)$"                              # message
)

# RFC 5424: <priority>version timestamp hostname app-name procid msgid structured-data msg
RFC5424_RE = re.compile(
    r"^<(\d+)>"                          # priority
    r"(\d+)\s+"                           # version
    r"(\S+)\s+"                           # timestamp
    r"(\S+)\s+"                           # hostname
    r"(\S+)\s+"                           # app-name
    r"(\S+)\s+"                           # procid
    r"(\S+)\s+"                           # msgid
    r"(\S+)\s+"                           # structured-data
    r"(.*)$"                              # message
)


@pydantic.dataclasses.dataclass
class SyslogProviderAuthConfig:
    """Syslog authentication configuration."""

    host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "Host to listen on",
            "hint": "e.g. 0.0.0.0",
        },
    )

    port: int = dataclasses.field(
        default=514,
        metadata={
            "required": False,
            "description": "TCP port to listen on",
            "hint": "Default: 514 (standard syslog port)",
        },
    )


class SyslogProvider(BaseProvider):
    """Ingest syslog messages received on a TCP port."""

    PROVIDER_CATEGORY = ["Infrastructure"]
    PROVIDER_DISPLAY_NAME = "Syslog"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_syslog",
            mandatory=True,
            alias="Receive Syslog",
        )
    ]
    PROVIDER_TAGS = ["monitoring", "syslog"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self._server = None
        self._loop = None

    def validate_config(self):
        self.authentication_config = SyslogProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        return {"receive_syslog": True}

    def dispose(self):
        self.stop_consume()

    @staticmethod
    def _parse_priority(priority: int) -> tuple[int, int, str, str]:
        """Parse syslog priority into facility and severity."""
        facility = priority >> 3
        severity = priority & 0x07
        facility_name = SYSLOG_FACILITY_NAMES.get(facility, f"unknown-{facility}")
        severity_name = SYSLOG_SEVERITY_NAMES.get(severity, f"unknown-{severity}")
        return facility, severity, facility_name, severity_name

    @staticmethod
    def _map_severity(severity: int) -> str:
        """Map syslog severity to Keep alert severity."""
        return SYSLOG_SEVERITY_MAP.get(severity, "info")

    def _parse_syslog_message(self, raw: str) -> dict | None:
        """Parse a raw syslog message string into an alert dict."""
        raw = raw.strip()
        if not raw:
            return None

        # Try RFC 5424 first (has version number after priority)
        match = RFC5424_RE.match(raw)
        if match:
            priority = int(match.group(1))
            timestamp = match.group(3)
            hostname = match.group(4)
            app_name = match.group(5)
            pid = match.group(6)
            message = match.group(9)
        else:
            # Try RFC 3164
            match = RFC3164_RE.match(raw)
            if match:
                priority = int(match.group(1))
                timestamp = match.group(2)
                hostname = match.group(3)
                app_name = match.group(4)
                pid = match.group(5) or ""
                message = match.group(6)
            else:
                # Fallback: treat entire line as message with minimal parsing
                self.logger.warning(f"Could not parse syslog message: {raw[:100]}")
                # Try to extract just the priority
                pri_match = re.match(r"^<(\d+)>", raw)
                if pri_match:
                    priority = int(pri_match.group(1))
                    message = raw[pri_match.end():].strip()
                else:
                    priority = 6  # informational
                    message = raw
                facility, severity, facility_name, severity_name = self._parse_priority(priority)
                return {
                    "name": f"syslog - {message[:50]}",
                    "message": message,
                    "severity": self._map_severity(severity),
                    "source": "syslog",
                    "syslog_facility": facility_name,
                    "syslog_severity": severity_name,
                    "syslog_hostname": "",
                    "syslog_app_name": "",
                    "syslog_pid": "",
                    "syslog_timestamp": "",
                }

        facility, severity, facility_name, severity_name = self._parse_priority(priority)

        return {
            "name": f"{app_name} - {message[:50]}",
            "message": message,
            "severity": self._map_severity(severity),
            "source": "syslog",
            "syslog_facility": facility_name,
            "syslog_severity": severity_name,
            "syslog_hostname": hostname,
            "syslog_app_name": app_name,
            "syslog_pid": pid,
            "syslog_timestamp": timestamp,
        }

    async def _handle_connection(self, reader, writer):
        """Handle a single TCP connection."""
        peer = writer.get_extra_info("peername")
        try:
            while self.consume:
                data = await reader.read(4096)
                if not data:
                    break
                text = data.decode("utf-8", errors="replace")
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    alert = self._parse_syslog_message(line)
                    if alert:
                        try:
                            self._push_alert(alert)
                        except Exception:
                            self.logger.warning(
                                "Error pushing syslog alert",
                                extra={"peer": peer, "line": line[:100]},
                            )
        except Exception:
            self.logger.exception(f"Error handling syslog connection from {peer}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _run_server(self):
        """Run the TCP server."""
        host = self.authentication_config.host
        port = self.authentication_config.port
        self._server = await asyncio.start_server(
            self._handle_connection, host, port
        )
        self.logger.info(f"Syslog TCP server listening on {host}:{port}")
        async with self._server:
            await self._server.serve_forever()

    def start_consume(self):
        """Start listening for syslog messages on TCP port."""
        self.consume = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_server())
        except Exception:
            self.logger.exception("Syslog TCP server error")
        finally:
            self._loop.close()
            self._loop = None

    def stop_consume(self):
        """Stop listening for syslog messages."""
        self.consume = False
        if self._server:
            self._server.close()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

    os.environ["KEEP_API_URL"] = "http://localhost:8080"

    from keep.api.core.dependencies import SINGLE_TENANT_UUID

    context_manager = ContextManager(tenant_id=SINGLE_TENANT_UUID)
    config = {
        "authentication": {
            "host": "0.0.0.0",
            "port": 514,
        }
    }
    from keep.providers.providers_factory import ProvidersFactory

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="syslog-keephq",
        provider_type="syslog",
        provider_config=config,
    )
    provider.start_consume()
