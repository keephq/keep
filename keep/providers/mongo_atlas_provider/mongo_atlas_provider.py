"""
MongoAtlasProvider is a provider that integrates Keep with MongoDB Atlas Alerts.
It supports receiving alerts via webhook and querying active/open alerts from Atlas API.
"""

import dataclasses
import logging
from datetime import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class MongoAtlasProviderAuthConfig:
    """
    MongoDB Atlas provider authentication configuration.
    Requires Programmatic API Key (public + private) and a project/group ID.
    Reference: https://www.mongodb.com/docs/atlas/configure-api-access/
    """

    public_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas public API key",
            "hint": "Found under Atlas > Organization > API Keys",
        }
    )
    private_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas private API key",
            "hint": "Found under Atlas > Organization > API Keys",
            "sensitive": True,
        }
    )
    group_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas Project/Group ID",
            "hint": "Found in the Atlas URL: https://cloud.mongodb.com/v2/<group_id>",
        }
    )


class MongoAtlasProvider(BaseProvider):
    """Get alerts from MongoDB Atlas and receive alert webhooks into Keep."""

    PROVIDER_DISPLAY_NAME = "MongoDB Atlas"
    PROVIDER_CATEGORY = ["Database", "Cloud Infrastructure"]
    PROVIDER_TAGS = ["alert"]
    ATLAS_BASE_URL = "https://cloud.mongodb.com/api/atlas/v2"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="project:read",
            description="Required to read alerts from a project",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://www.mongodb.com/docs/atlas/configure-api-access/#std-label-atlas-prog-api-key",
            alias="Project Viewer",
        ),
        ProviderScope(
            name="webhook:manage",
            description="Required to setup alert webhook integrations",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://www.mongodb.com/docs/atlas/configure-alerts/",
            alias="Project Owner",
        ),
    ]

    SEVERITIES_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "HIGH": AlertSeverity.HIGH,
        "MEDIUM": AlertSeverity.WARNING,
        "LOW": AlertSeverity.LOW,
        "INFORMATIONAL": AlertSeverity.INFO,
        "INFO": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "OPEN": AlertStatus.FIRING,
        "TRACKING": AlertStatus.FIRING,
        "RESOLVED": AlertStatus.RESOLVED,
        "CLOSED": AlertStatus.RESOLVED,
        "ACKNOWLEDGED": AlertStatus.ACKNOWLEDGED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validates required configuration for MongoDB Atlas provider."""
        self.authentication_config = MongoAtlasProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """Nothing to dispose here."""
        pass

    @property
    def __auth(self):
        """Returns Digest Auth tuple for Atlas API."""
        return (
            self.authentication_config.public_key,
            self.authentication_config.private_key,
        )

    @property
    def __headers(self):
        return {"Accept": "application/vnd.atlas.2023-01-01+json"}

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {scope.name: "Invalid" for scope in self.PROVIDER_SCOPES}
        try:
            response = requests.get(
                f"{self.ATLAS_BASE_URL}/groups/{self.authentication_config.group_id}/alerts",
                auth=self.__auth,
                headers=self.__headers,
            )
            if response.ok:
                scopes["project:read"] = True
            else:
                scopes["project:read"] = response.text
        except Exception as e:
            scopes["project:read"] = str(e)

        # We won't check webhook scope here — it's only needed during webhook setup
        scopes["webhook:manage"] = True
        return scopes

    def get_alerts(self) -> list[AlertDto]:
        """Fetches all open/firing alerts from MongoDB Atlas."""
        try:
            response = requests.get(
                f"{self.ATLAS_BASE_URL}/groups/{self.authentication_config.group_id}/alerts",
                auth=self.__auth,
                headers=self.__headers,
                params={"status": "OPEN"},
            )
            response.raise_for_status()
            data = response.json()
            alerts = data.get("results", [])
            return [self._format_alert(a) for a in alerts]
        except Exception:
            self.logger.exception("Failed to get alerts from MongoDB Atlas")
            return []

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "MongoAtlasProvider" = None
    ) -> AlertDto:
        """
        Formats a MongoDB Atlas alert webhook payload (or API response) into Keep AlertDto.
        Reference: https://www.mongodb.com/docs/atlas/alert-basics/
        """
        logger = logging.getLogger(__name__)
        logger.info("Formatting MongoDB Atlas alert")

        # Map status
        raw_status = event.get("status", "OPEN")
        status = MongoAtlasProvider.STATUS_MAP.get(
            raw_status.upper(), AlertStatus.FIRING
        )

        # Map severity from alert type or typeName
        raw_severity = (
            event.get("severity")
            or event.get("typeName", "INFO")
        )
        severity = MongoAtlasProvider.SEVERITIES_MAP.get(
            raw_severity.upper(), AlertSeverity.INFO
        )

        # Parse timestamps
        created_at = event.get("created")
        updated_at = event.get("updated")
        resolved_at = event.get("resolved")

        def parse_ts(ts):
            if ts:
                try:
                    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").isoformat()
                except Exception:
                    return ts
            return None

        last_received = parse_ts(updated_at) or parse_ts(created_at)

        # Compose alert name
        alert_type = event.get("eventTypeName", event.get("typeName", "Alert"))
        hostname = event.get("hostnameAndPort") or event.get("replicaSetName") or ""
        name = f"{alert_type} - {hostname}".strip(" -") if hostname else alert_type

        # Build description
        description = (
            f"Cluster: {event.get('clusterName', 'N/A')}, "
            f"Metric: {event.get('metricName', 'N/A')}, "
            f"Current value: {event.get('currentValue', {}).get('number', 'N/A')} "
            f"{event.get('currentValue', {}).get('units', '')}"
        )

        return AlertDto(
            id=event.get("id", ""),
            name=name,
            status=status,
            severity=severity,
            description=description,
            lastReceived=last_received,
            createdAt=parse_ts(created_at),
            resolvedAt=parse_ts(resolved_at),
            source=["mongoatlas"],
            url=event.get("links", [{}])[0].get("href", ""),
            group_id=event.get("groupId"),
            cluster_name=event.get("clusterName"),
            replica_set=event.get("replicaSetName"),
            host=event.get("hostnameAndPort"),
            metric_name=event.get("metricName"),
            acknowledgement=event.get("acknowledgement"),
            payload=event,
        )


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="keeptest",
        workflow_id="test",
    )
    config = ProviderConfig(
        authentication={
            "public_key": os.environ.get("ATLAS_PUBLIC_KEY"),
            "private_key": os.environ.get("ATLAS_PRIVATE_KEY"),
            "group_id": os.environ.get("ATLAS_GROUP_ID"),
        }
    )
    provider = MongoAtlasProvider(context_manager, "mongo-atlas-test", config)
    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} alerts")
    for a in alerts:
        print(a)
