"""
SolarWinds Provider is a class that allows to ingest/digest data from SolarWinds.
"""

import dataclasses
import datetime
import logging

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    SolarWinds authentication configuration.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Server URL",
            "hint": "https://solarwinds.example.com:17778",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Username",
            "sensitive": False,
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Password",
            "sensitive": True,
        }
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class SolarwindsProvider(BaseProvider):
    """Pull alerts from SolarWinds Orion into Keep."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authenticated",
            mandatory=True,
        ),
        ProviderScope(
            name="read_alerts",
            description="Read active alerts from SolarWinds",
            mandatory=True,
            documentation_url="https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-managing-alerts-sw1498.htm",
        ),
    ]

    # SolarWinds severity mapping
    # https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-alerts-severity-levels-sw712.htm
    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,        # Informational
        1: AlertSeverity.WARNING,     # Warning
        2: AlertSeverity.CRITICAL,    # Critical
        3: AlertSeverity.LOW,         # Notice
    }

    STATUS_MAP = {
        0: AlertStatus.FIRING,       # Not Acknowledged
        1: AlertStatus.ACKNOWLEDGED,  # Acknowledged
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for SolarWinds provider.
        """
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        """
        validated_scopes = {}
        try:
            # Test basic connectivity with a simple SWIS query
            self.__swis_query("SELECT TOP 1 NodeID FROM Orion.Nodes")
            validated_scopes["authenticated"] = True
        except Exception as e:
            validated_scopes["authenticated"] = str(e)

        try:
            self.__swis_query(
                "SELECT TOP 1 AlertActiveID FROM Orion.AlertActive"
            )
            validated_scopes["read_alerts"] = True
        except Exception as e:
            validated_scopes["read_alerts"] = str(e)

        return validated_scopes

    def __swis_query(self, query: str, params: dict = None) -> dict:
        """
        Execute a SWIS (SolarWinds Information Service) query.

        The SWIS REST API is the standard way to query SolarWinds Orion.
        Documentation: https://github.com/solarwinds/OrionSDK/wiki/About-SWIS

        Args:
            query (str): The SWQL query to execute.
            params (dict): Optional query parameters.

        Returns:
            dict: The response from the SWIS API.
        """
        url = f"{self.authentication_config.host_url}/SolarWinds/InformationService/v3/Json/Query"

        request_params = {"query": query}
        if params:
            request_params["parameters"] = params

        response = requests.get(
            url,
            params=request_params,
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            verify=self.authentication_config.verify,
            headers={"Content-Type": "application/json"},
        )

        try:
            response.raise_for_status()
        except requests.HTTPError:
            self.logger.error(
                "Error while querying SolarWinds SWIS API",
                extra={
                    "status_code": response.status_code,
                    "response": response.text,
                    "tenant_id": self.context_manager.tenant_id,
                },
            )
            raise

        return response.json()

    def __swis_invoke(self, entity: str, verb: str, body: list = None) -> dict:
        """
        Invoke a SWIS verb (action) on an entity.

        Args:
            entity (str): The entity URI.
            verb (str): The verb to invoke.
            body (list): Optional body parameters.

        Returns:
            dict: The response from the SWIS API.
        """
        url = f"{self.authentication_config.host_url}/SolarWinds/InformationService/v3/Json/Invoke/{entity}/{verb}"

        response = requests.post(
            url,
            json=body or [],
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            verify=self.authentication_config.verify,
            headers={"Content-Type": "application/json"},
        )

        try:
            response.raise_for_status()
        except requests.HTTPError:
            self.logger.error(
                "Error while invoking SolarWinds SWIS verb",
                extra={
                    "entity": entity,
                    "verb": verb,
                    "status_code": response.status_code,
                    "response": response.text,
                    "tenant_id": self.context_manager.tenant_id,
                },
            )
            raise

        return response.json() if response.text else {}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get active alerts from SolarWinds using the SWIS API.

        Uses the Orion.AlertActive, Orion.AlertConfigurations, and Orion.AlertHistory
        tables to get comprehensive alert information.
        """
        self.logger.info("Collecting active alerts from SolarWinds")

        # Query active alerts with their configuration details
        query = """
            SELECT
                aa.AlertActiveID,
                aa.AlertObjectID,
                aa.TriggeredDateTime,
                aa.TriggeredMessage,
                aa.NumberOfNotes,
                aa.Acknowledged,
                aa.AcknowledgedBy,
                aa.AcknowledgedDateTime,
                aa.AcknowledgedNote,
                ac.Name AS AlertName,
                ac.Description AS AlertDescription,
                ac.Severity,
                ac.ObjectType,
                ac.Enabled,
                ao.EntityUri,
                ao.EntityType,
                ao.RelatedNodeUri,
                ao.RelatedNodeCaption
            FROM Orion.AlertActive aa
            INNER JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
            INNER JOIN Orion.AlertConfigurations ac ON ao.AlertID = ac.AlertID
            WHERE ac.Enabled = true
        """

        try:
            response = self.__swis_query(query)
        except Exception as e:
            self.logger.error(
                "Failed to get alerts from SolarWinds",
                extra={"error": str(e)},
            )
            raise

        results = response.get("results", [])
        formatted_alerts = []

        for alert in results:
            try:
                alert_id = str(alert.get("AlertActiveID", ""))
                name = alert.get("AlertName", "Unknown Alert")
                description = alert.get("AlertDescription", "") or alert.get(
                    "TriggeredMessage", ""
                )
                message = alert.get("TriggeredMessage", name)

                # Map severity
                severity_value = alert.get("Severity", 0)
                severity = self.SEVERITIES_MAP.get(severity_value, AlertSeverity.INFO)

                # Map status based on acknowledgement
                acknowledged = alert.get("Acknowledged", False)
                if acknowledged:
                    status = AlertStatus.ACKNOWLEDGED
                else:
                    status = AlertStatus.FIRING

                # Parse triggered date time
                triggered_dt = alert.get("TriggeredDateTime")
                if triggered_dt:
                    try:
                        last_received = datetime.datetime.fromisoformat(
                            triggered_dt.replace("Z", "+00:00")
                        ).isoformat()
                    except (ValueError, AttributeError):
                        last_received = datetime.datetime.now(
                            tz=datetime.timezone.utc
                        ).isoformat()
                else:
                    last_received = datetime.datetime.now(
                        tz=datetime.timezone.utc
                    ).isoformat()

                # Build node/service information
                node_caption = alert.get("RelatedNodeCaption", "")
                entity_type = alert.get("EntityType", "")
                object_type = alert.get("ObjectType", "")

                formatted_alerts.append(
                    AlertDto(
                        id=alert_id,
                        name=name,
                        description=description,
                        message=message,
                        status=status,
                        severity=severity,
                        lastReceived=last_received,
                        source=["solarwinds"],
                        service=node_caption,
                        acknowledged=acknowledged,
                        acknowledgedBy=alert.get("AcknowledgedBy"),
                        entity_type=entity_type,
                        object_type=object_type,
                        alert_object_id=str(alert.get("AlertObjectID", "")),
                        entity_uri=alert.get("EntityUri", ""),
                    )
                )
            except Exception as e:
                self.logger.error(
                    "Failed to format SolarWinds alert",
                    extra={
                        "alert_active_id": alert.get("AlertActiveID"),
                        "error": str(e),
                    },
                )
                continue

        self.logger.info(
            "Collected alerts from SolarWinds",
            extra={"alert_count": len(formatted_alerts)},
        )
        return formatted_alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an incoming SolarWinds webhook alert event to AlertDto.

        SolarWinds can send alerts via webhook with custom payloads.
        This method handles the common fields that would be present
        in a webhook payload from SolarWinds.
        """
        alert_id = event.get("AlertActiveID", event.get("id", ""))
        name = event.get("AlertName", event.get("name", "SolarWinds Alert"))
        description = event.get("AlertDescription", event.get("description", ""))
        message = event.get("AlertMessage", event.get("message", name))

        # Map severity
        severity_value = event.get("Severity", event.get("severity", 0))
        if isinstance(severity_value, str):
            severity_map_str = {
                "informational": AlertSeverity.INFO,
                "warning": AlertSeverity.WARNING,
                "critical": AlertSeverity.CRITICAL,
                "notice": AlertSeverity.LOW,
                "serious": AlertSeverity.HIGH,
                "info": AlertSeverity.INFO,
            }
            severity = severity_map_str.get(
                severity_value.lower(), AlertSeverity.INFO
            )
        else:
            severity = SolarwindsProvider.SEVERITIES_MAP.get(
                severity_value, AlertSeverity.INFO
            )

        # Map status
        status_value = event.get("Acknowledged", event.get("acknowledged", False))
        alert_status_raw = event.get("status", "").lower()
        if alert_status_raw == "resolved":
            status = AlertStatus.RESOLVED
        elif alert_status_raw == "acknowledged" or status_value:
            status = AlertStatus.ACKNOWLEDGED
        else:
            status = AlertStatus.FIRING

        # Parse time
        triggered_dt = event.get(
            "TriggeredDateTime",
            event.get("lastReceived"),
        )
        if triggered_dt:
            try:
                if isinstance(triggered_dt, str):
                    last_received = datetime.datetime.fromisoformat(
                        triggered_dt.replace("Z", "+00:00")
                    ).isoformat()
                else:
                    last_received = datetime.datetime.now(
                        tz=datetime.timezone.utc
                    ).isoformat()
            except (ValueError, AttributeError):
                last_received = datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat()
        else:
            last_received = datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat()

        # Extract node/service info
        node_caption = event.get(
            "NodeName",
            event.get("RelatedNodeCaption", event.get("service", "")),
        )

        environment = event.get("environment", "unknown")

        return AlertDto(
            id=str(alert_id),
            name=name,
            description=description,
            message=message,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["solarwinds"],
            pushed=True,
            service=node_caption,
            environment=environment,
            acknowledged=status_value,
            entity_type=event.get("EntityType", ""),
            object_type=event.get("ObjectType", ""),
            url=event.get("url"),
        )


if __name__ == "__main__":
    # Output debug messages
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    host_url = os.environ.get("SOLARWINDS_HOST_URL")
    username = os.environ.get("SOLARWINDS_USERNAME")
    password = os.environ.get("SOLARWINDS_PASSWORD")

    provider_config = {
        "authentication": {
            "host_url": host_url,
            "username": username,
            "password": password,
            "verify": False,
        },
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="solarwinds",
        provider_type="solarwinds",
        provider_config=provider_config,
    )

    alerts = provider.get_alerts()
    print(alerts)
