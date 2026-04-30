"""
SolarWinds Provider - pull alerts from SolarWinds Orion via the SWIS REST API
and receive webhook notifications.
"""

import dataclasses
from datetime import datetime, timezone

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    SolarWinds Orion authentication configuration.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion server URL",
            "hint": "e.g. https://orion.example.com:17778",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion username",
            "hint": "Admin account with API access",
            "sensitive": False,
        }
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion password",
            "sensitive": True,
        }
    )

    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificates (disable for self-signed certs)",
            "hint": "Set to false if using self-signed certs",
        },
    )


class SolarwindsProvider(BaseProvider):
    """
    Pull alerts from SolarWinds Orion and receive webhook notifications.
    """

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_ICON = "solarwinds-icon.png"
    WEBHOOK_INSTALLATION_REQUIRED = True

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from SolarWinds Orion to Keep, create an HTTP POST alert action:

1. Go to **Settings > All Settings > Alerts & Reports > Manage Alerts**
2. Edit or create an alert, go to the **Trigger Actions** tab
3. Add a **Send a GET or POST Request to a URL** action
4. Set the URL to `{keep_webhook_api_url}`
5. Set method to POST, content type to `application/json`
6. Add header `X-API-KEY: <your Keep API key>`
7. Use SolarWinds variables in the JSON body (see docs for a template)
    """

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from SolarWinds Orion via SWIS API",
        ),
    ]

    # SolarWinds severity levels:
    # Orion uses numeric severity in AlertActive, common values:
    # 0 = Informational, 1 = Warning, 2 = Critical/Serious, 3 = Down
    SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.CRITICAL,
        "information": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "notice": AlertSeverity.LOW,
        "warning": AlertSeverity.WARNING,
        "minor": AlertSeverity.WARNING,
        "serious": AlertSeverity.HIGH,
        "major": AlertSeverity.HIGH,
        "critical": AlertSeverity.CRITICAL,
    }

    STATUS_MAP = {
        True: AlertStatus.FIRING,
        False: AlertStatus.RESOLVED,
        "triggered": AlertStatus.FIRING,
        "reset": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def _get_auth(self):
        return HTTPBasicAuth(
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def _swql_query(self, query: str) -> list[dict]:
        """Run a SWQL query against the SWIS REST API."""
        url = f"{self.authentication_config.host_url}/SolarWinds/InformationService/v3/Json/Query"
        params = {"query": query}
        resp = requests.get(
            url,
            params=params,
            auth=self._get_auth(),
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def validate_scopes(self):
        self.logger.info("Validating SolarWinds scopes")
        try:
            # simple query to check connectivity
            self._swql_query("SELECT TOP 1 NodeID FROM Orion.Nodes")
            self.logger.info("SolarWinds scope validation passed")
            return {"read_alerts": True}
        except Exception as e:
            self.logger.exception("Failed to validate SolarWinds scopes")
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """Pull active alerts from SolarWinds Orion."""
        self.logger.info("Pulling alerts from SolarWinds Orion")
        alerts = []

        try:
            # Fetch active alerts with node and object info
            query = (
                "SELECT a.AlertActiveID, a.TriggeredDateTime, a.Acknowledged, "
                "a.AlertObject.AlertName, a.AlertObject.Severity, "
                "a.AlertObject.EntityCaption, a.AlertObject.EntityUri, "
                "a.AlertObject.AlertConfigurations.Description "
                "FROM Orion.AlertActive a"
            )
            results = self._swql_query(query)

            for row in results:
                alert_name = row.get("AlertName", "Unknown Alert")
                entity = row.get("EntityCaption", "")
                severity_val = row.get("Severity", 0)
                acknowledged = row.get("Acknowledged", False)
                triggered = row.get("TriggeredDateTime")
                description = row.get("Description", "")
                alert_id = str(row.get("AlertActiveID", ""))

                timestamp = None
                if triggered:
                    try:
                        timestamp = datetime.fromisoformat(
                            triggered.replace("Z", "+00:00")
                        ).isoformat()
                    except (ValueError, AttributeError):
                        timestamp = triggered

                if acknowledged:
                    status = AlertStatus.ACKNOWLEDGED
                else:
                    status = AlertStatus.FIRING

                sev_key = severity_val
                if isinstance(severity_val, str):
                    sev_key = severity_val.lower()

                alerts.append(
                    AlertDto(
                        id=alert_id,
                        name=alert_name,
                        status=status,
                        severity=self.SEVERITY_MAP.get(sev_key, AlertSeverity.INFO),
                        description=description or f"{alert_name} on {entity}",
                        hostname=entity,
                        timestamp=timestamp,
                        source=["solarwinds"],
                    )
                )

            # Also fetch nodes in a warning/critical state
            node_query = (
                "SELECT n.NodeID, n.Caption, n.Status, n.StatusDescription, "
                "n.LastSystemUpTimePollUtc "
                "FROM Orion.Nodes n WHERE n.Status != 1"
            )
            nodes = self._swql_query(node_query)

            # Orion node status: 1=Up, 2=Down, 3=Warning, 4=Shutdown, etc.
            node_severity = {
                2: AlertSeverity.CRITICAL,
                3: AlertSeverity.WARNING,
                4: AlertSeverity.INFO,
            }
            node_status_map = {
                2: AlertStatus.FIRING,
                3: AlertStatus.FIRING,
                4: AlertStatus.RESOLVED,
            }

            for node in nodes:
                node_status = node.get("Status", 1)
                caption = node.get("Caption", "")
                status_desc = node.get("StatusDescription", "")
                poll_time = node.get("LastSystemUpTimePollUtc")

                timestamp = None
                if poll_time:
                    try:
                        timestamp = datetime.fromisoformat(
                            poll_time.replace("Z", "+00:00")
                        ).isoformat()
                    except (ValueError, AttributeError):
                        timestamp = poll_time

                alerts.append(
                    AlertDto(
                        id=f"node-{node.get('NodeID', '')}",
                        name=f"Node {caption} is {status_desc}",
                        status=node_status_map.get(node_status, AlertStatus.FIRING),
                        severity=node_severity.get(node_status, AlertSeverity.WARNING),
                        description=f"{caption}: {status_desc}",
                        hostname=caption,
                        timestamp=timestamp,
                        source=["solarwinds"],
                    )
                )

        except Exception as e:
            self.logger.exception("Failed to pull alerts from SolarWinds")
            raise Exception(f"Error pulling SolarWinds alerts: {e}")

        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a SolarWinds webhook payload into a Keep AlertDto.
        SolarWinds alert actions can POST JSON with variable substitution.
        """
        event = event or {}

        alert_name = event.get("AlertName") or event.get("alert_name", "SolarWinds Alert")
        node_name = event.get("NodeName") or event.get("node_name", "")
        entity = event.get("EntityCaption") or event.get("entity_caption", node_name)
        message = event.get("Message") or event.get("message", "")
        severity_str = event.get("Severity") or event.get("severity", "")
        alert_obj_id = event.get("AlertObjectID") or event.get("alert_object_id", "")
        triggered_dt = event.get("TriggeredDateTime") or event.get("triggered_datetime")
        alert_url = event.get("AlertDetailsUrl") or event.get("alert_details_url", "")
        is_ack = event.get("IsAcknowledged") or event.get("is_acknowledged", False)
        is_active = event.get("IsActive")
        if is_active is None:
            is_active = event.get("is_active", True)
        notification_type = event.get("NotificationType") or event.get("notification_type", "")

        # figure out status
        if isinstance(is_ack, str):
            is_ack = is_ack.lower() in ("true", "1", "yes")
        if isinstance(is_active, str):
            is_active = is_active.lower() in ("true", "1", "yes")

        if is_ack:
            status = AlertStatus.ACKNOWLEDGED
        elif not is_active:
            status = AlertStatus.RESOLVED
        elif notification_type.lower() == "reset":
            status = AlertStatus.RESOLVED
        else:
            status = AlertStatus.FIRING

        # figure out severity
        sev_key = severity_str
        if isinstance(severity_str, str):
            sev_key = severity_str.lower()
        try:
            sev_key = int(sev_key)
        except (ValueError, TypeError):
            pass

        severity = SolarwindsProvider.SEVERITY_MAP.get(sev_key, AlertSeverity.INFO)

        alert_id = str(alert_obj_id) if alert_obj_id else f"{alert_name}-{node_name}"

        return AlertDto(
            id=alert_id,
            name=alert_name,
            status=status,
            severity=severity,
            description=message or f"{alert_name} on {entity}",
            hostname=node_name or entity,
            service_name=entity if entity != node_name else None,
            timestamp=triggered_dt,
            source=["solarwinds"],
            url=alert_url or None,
            notification_type=notification_type or None,
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG)
    context_manager = ContextManager(
        tenant_id="test", workflow_id="test", workflow_execution_id="test"
    )

    config = ProviderConfig(
        description="SolarWinds Provider",
        authentication={
            "host_url": os.environ.get("SOLARWINDS_HOST", "https://orion.example.com:17778"),
            "username": os.environ.get("SOLARWINDS_USER", "admin"),
            "password": os.environ.get("SOLARWINDS_PASS", ""),
        },
    )

    provider = SolarwindsProvider(context_manager, "solarwinds-test", config)
    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} alerts")
