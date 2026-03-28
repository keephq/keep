"""
MongoAtlasProvider integrates Keep with MongoDB Atlas cloud monitoring alerts.

MongoDB Atlas (https://www.mongodb.com/atlas) provides a managed cloud database
service with built-in monitoring and alerting. This provider supports:

  1. Pulling active alerts via the Atlas API v2 with HTTP Digest authentication.
  2. Receiving alerts via Atlas webhook notifications (push-based).

References:
  - https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Alerts
  - https://www.mongodb.com/docs/atlas/configure-alerts/
  - https://www.mongodb.com/docs/atlas/alert-basics/
"""

import dataclasses
import datetime

import pydantic
import requests
from requests.auth import HTTPDigestAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class MongoAtlasProviderAuthConfig:
    """
    MongoDB Atlas authentication configuration.

    Atlas uses HTTP Digest Auth (public key + private key pair).
    The group_id is the Atlas Project ID found in the project settings URL.
    """

    public_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas public API key",
            "hint": "Found in Atlas Organization → Access Manager → API Keys",
        }
    )
    private_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas private API key",
            "hint": "Shown once at API key creation — store securely",
            "sensitive": True,
        }
    )
    group_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas Project ID (group ID)",
            "hint": "Found in Atlas Project Settings → Project ID",
        }
    )


class MongoAtlasProvider(BaseProvider):
    """Pull and receive alerts from MongoDB Atlas into Keep.

    Supports two integration modes:
      - **Pull**: polls the Atlas Alerts API (`/api/atlas/v2/groups/{group_id}/alerts`)
        for open alerts using HTTP Digest Auth.
      - **Push (webhook)**: Atlas sends alert notifications directly to Keep's
        webhook endpoint when an alert is opened or resolved.
    """

    PROVIDER_DISPLAY_NAME = "MongoDB Atlas"
    PROVIDER_CATEGORY = ["Database", "Monitoring"]
    PROVIDER_TAGS = ["alert", "database", "cloud"]

    ATLAS_API_BASE = "https://cloud.mongodb.com/api/atlas/v2"

    # Atlas alert severity mapping based on alert type prefix patterns
    # Reference: https://www.mongodb.com/docs/atlas/alert-basics/#alert-severity
    SEVERITIES_MAP: dict[str, AlertSeverity] = {
        # Explicit severity fields in webhook payloads
        "CRITICAL": AlertSeverity.CRITICAL,
        "HIGH": AlertSeverity.HIGH,
        "MEDIUM": AlertSeverity.WARNING,
        "WARNING": AlertSeverity.WARNING,
        "LOW": AlertSeverity.INFO,
        "INFO": AlertSeverity.INFO,
        "INFORMATIONAL": AlertSeverity.INFO,
        # Status-based mapping (pull mode)
        "OPEN": AlertSeverity.HIGH,
        "TRACKING": AlertSeverity.WARNING,
        "CLOSED": AlertSeverity.INFO,
    }

    STATUS_MAP: dict[str, AlertStatus] = {
        "OPEN": AlertStatus.FIRING,
        "TRACKING": AlertStatus.FIRING,
        "CLOSED": AlertStatus.RESOLVED,
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts_read",
            description="Read alerts from Atlas project",
            mandatory=True,
            alias="Project Read Only",
        )
    ]

    FINGERPRINT_FIELDS = ["id"]

    # Webhook setup instructions
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
## Setting up MongoDB Atlas webhook to send alerts to Keep

1. Log in to [MongoDB Atlas](https://cloud.mongodb.com/) and go to your **Project**.
2. Navigate to **Project Settings** → **Alerts** → **Notification Settings**.
3. Click **+ Add** to create a new notification channel.
4. Choose **Webhook** as the notification method.
5. Set the **Webhook URL** to:
   ```
   {keep_webhook_api_url}
   ```
6. Under **Secret**, add the following HTTP header:
   - **Header Name**: `X-API-KEY`
   - **Header Value**: `{api_key}`
7. Save and enable the notification channel.
8. Assign the webhook to your alert conditions under **Project Settings → Alerts → Alert Conditions**.

Atlas will now send alert payloads to Keep whenever an alert opens or resolves.
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validates required configuration for the MongoDB Atlas provider."""
        self.authentication_config = MongoAtlasProviderAuthConfig(
            **self.config.authentication
        )

    def _get_auth(self) -> HTTPDigestAuth:
        """Returns HTTP Digest Auth credentials for Atlas API requests."""
        return HTTPDigestAuth(
            self.authentication_config.public_key,
            self.authentication_config.private_key,
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validates connectivity and API access by listing project details."""
        validated = {"alerts_read": True}
        try:
            response = requests.get(
                f"{self.ATLAS_API_BASE}/groups/{self.authentication_config.group_id}",
                auth=self._get_auth(),
                headers={"Accept": "application/vnd.atlas.2023-01-01+json"},
                timeout=10,
            )
            response.raise_for_status()
        except Exception as e:
            validated["alerts_read"] = str(e)
        return validated

    def _get_alerts(self) -> list[AlertDto]:
        """Fetches open alerts from the MongoDB Atlas Alerts API.

        Returns:
            List of AlertDto objects representing open Atlas alerts.
        """
        self.logger.info(
            "Fetching open alerts from MongoDB Atlas",
            extra={"group_id": self.authentication_config.group_id},
        )
        url = f"{self.ATLAS_API_BASE}/groups/{self.authentication_config.group_id}/alerts"
        response = requests.get(
            url,
            auth=self._get_auth(),
            headers={"Accept": "application/vnd.atlas.2023-01-01+json"},
            params={"status": "OPEN"},
            timeout=30,
        )
        response.raise_for_status()
        alerts_data = response.json().get("results", [])
        return [self._alert_to_dto(alert) for alert in alerts_data]

    def _alert_to_dto(self, alert: dict) -> AlertDto:
        """Converts a raw Atlas API alert dict to an AlertDto."""
        alert_id = alert.get("id", "")
        event_type = alert.get("eventTypeName", "UNKNOWN_ALERT")
        status_raw = alert.get("status", "OPEN")

        status = self.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        # Severity: try 'severity' field first (present in newer Atlas API responses),
        # fall back to status-based mapping
        severity_raw = alert.get("severity", status_raw)
        severity = self.SEVERITIES_MAP.get(severity_raw.upper(), AlertSeverity.INFO)

        # Build a descriptive alert name from the event type
        # Atlas event types look like "REPLICATION_OPLOG_WINDOW_RUNNING_OUT",
        # "HOST_DOWN", "NO_PRIMARY", etc.
        name = event_type.replace("_", " ").title()

        # Description from human-readable field or metric details
        description = alert.get("humanReadable", name)
        if not description:
            metric_name = alert.get("metricName", "")
            current_value = alert.get("currentValue", {})
            if metric_name and current_value:
                units = current_value.get("units", "")
                value = current_value.get("number", "")
                description = f"{metric_name}: {value} {units}".strip()
            else:
                description = name

        # Hostname / cluster / resource information
        hostname = alert.get("hostnameAndPort", alert.get("hostname", ""))
        cluster_name = alert.get("clusterName", "")
        replica_set = alert.get("replicaSetName", "")

        service = cluster_name or hostname or ""

        last_received_raw = alert.get("updated") or alert.get("created")
        try:
            last_received = (
                datetime.datetime.fromisoformat(
                    str(last_received_raw).replace("Z", "+00:00")
                ).isoformat()
                if last_received_raw
                else datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
            )
        except (ValueError, TypeError):
            last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        alert_dto = AlertDto(
            id=alert_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            source=["mongoatlas"],
            service=service,
            lastReceived=last_received,
            labels={
                "event_type": event_type,
                "cluster_name": cluster_name,
                "hostname": hostname,
                "replica_set": replica_set,
                "group_id": alert.get("groupId", ""),
            },
        )

        alert_dto.fingerprint = MongoAtlasProvider.get_alert_fingerprint(
            alert_dto, fingerprint_fields=MongoAtlasProvider.FINGERPRINT_FIELDS
        )

        return alert_dto

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Converts an Atlas webhook notification payload into an AlertDto.

        Atlas webhook payloads use the same structure as the REST API response,
        with an additional `created` timestamp and nested alert details.

        Reference: https://www.mongodb.com/docs/atlas/configure-alerts/#configure-webhook-settings
        """
        # Atlas webhook notifications wrap the alert in an 'alerts' list
        # or deliver a single alert object directly
        if "alerts" in event:
            return [
                MongoAtlasProvider._format_single_atlas_alert(a)
                for a in event["alerts"]
            ]
        return MongoAtlasProvider._format_single_atlas_alert(event)

    @staticmethod
    def _format_single_atlas_alert(alert: dict) -> AlertDto:
        """Converts a single Atlas alert dict (webhook or API) to AlertDto."""
        alert_id = alert.get("id", "")
        event_type = alert.get("eventTypeName", "UNKNOWN_ALERT")
        status_raw = alert.get("status", "OPEN")

        name = event_type.replace("_", " ").title()
        description = alert.get("humanReadable", name) or name

        status = MongoAtlasProvider.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        severity_raw = alert.get("severity", status_raw)
        severity = MongoAtlasProvider.SEVERITIES_MAP.get(
            str(severity_raw).upper(), AlertSeverity.INFO
        )

        cluster_name = alert.get("clusterName", "")
        hostname = alert.get("hostnameAndPort", alert.get("hostname", ""))

        last_received_raw = alert.get("updated") or alert.get("created")
        try:
            last_received = (
                datetime.datetime.fromisoformat(
                    str(last_received_raw).replace("Z", "+00:00")
                ).isoformat()
                if last_received_raw
                else datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
            )
        except (ValueError, TypeError):
            last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        alert_dto = AlertDto(
            id=alert_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            source=["mongoatlas"],
            service=cluster_name or hostname or "",
            lastReceived=last_received,
            labels={
                "event_type": event_type,
                "cluster_name": cluster_name,
                "hostname": hostname,
                "group_id": alert.get("groupId", ""),
                "replica_set": alert.get("replicaSetName", ""),
            },
        )

        alert_dto.fingerprint = MongoAtlasProvider.get_alert_fingerprint(
            alert_dto, fingerprint_fields=MongoAtlasProvider.FINGERPRINT_FIELDS
        )

        return alert_dto

    def dispose(self):
        """Nothing to dispose."""
        pass


if __name__ == "__main__":
    pass
