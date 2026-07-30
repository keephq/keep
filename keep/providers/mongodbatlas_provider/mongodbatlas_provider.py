"""
MongodbatlasProvider is a class that allows to pull alerts from MongoDB Atlas
and to receive Atlas alert webhooks.
"""

import dataclasses
import datetime

import pydantic
import requests
from requests.auth import HTTPDigestAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class MongodbatlasProviderAuthConfig:
    """MongoDB Atlas authentication configuration."""

    api_public_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Atlas API public key",
            "hint": "Organization or project API key with Project Read Only access",
            "documentation_url": "https://www.mongodb.com/docs/atlas/configure-api-access/",
        }
    )
    api_private_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Atlas API private key",
            "sensitive": True,
        }
    )
    group_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Atlas project (group) ID",
            "hint": "24-character hexadecimal string, found under Project Settings",
        }
    )
    api_url: str = dataclasses.field(
        default="https://cloud.mongodb.com",
        metadata={
            "required": False,
            "description": "Atlas API base URL",
            "hint": "Change for MongoDB Atlas for Government (https://cloud.mongodbgov.com)",
        },
    )


class MongodbatlasProvider(BaseProvider):
    """Pull alerts from MongoDB Atlas and receive Atlas alert webhooks."""

    PROVIDER_DISPLAY_NAME = "MongoDB Atlas"
    PROVIDER_CATEGORY = ["Database", "Monitoring"]
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["id"]

    ATLAS_API_VERSION_HEADER = "application/vnd.atlas.2023-01-01+json"
    PAGE_SIZE = 500  # Atlas API maximum for itemsPerPage

    PROVIDER_SCOPES = [
        ProviderScope(
            name="Project Read Only",
            description="Read access to the project, required to list alerts",
            mandatory=True,
            documentation_url="https://www.mongodb.com/docs/atlas/reference/user-roles/#mongodb-authrole-Project-Read-Only",
            alias="Project Read Only",
        ),
    ]

    STATUS_MAP = {
        "OPEN": AlertStatus.FIRING,
        "TRACKING": AlertStatus.PENDING,
        "CLOSED": AlertStatus.RESOLVED,
        "CANCELLED": AlertStatus.RESOLVED,
    }

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from MongoDB Atlas to Keep:

1. In Atlas, go to your project and click Integrations.
2. Choose Webhook and click Configure.
3. Set the URL to {keep_webhook_api_url}?api_key={api_key}
4. Leave the secret empty (Keep authenticates via the api_key query parameter) and save.
5. In Alerts > Alert Settings, add or edit alert configurations and select Webhook as a notification method.

Atlas does not include a severity in webhook payloads, so alerts arrive with warning severity and can be re-mapped in Keep.
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MongodbatlasProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    @property
    def _auth(self) -> HTTPDigestAuth:
        return HTTPDigestAuth(
            self.authentication_config.api_public_key,
            self.authentication_config.api_private_key,
        )

    def _alerts_url(self) -> str:
        base = self.authentication_config.api_url.rstrip("/")
        return (
            f"{base}/api/atlas/v2/groups/{self.authentication_config.group_id}/alerts"
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            response = requests.get(
                self._alerts_url(),
                auth=self._auth,
                headers={"Accept": self.ATLAS_API_VERSION_HEADER},
                params={"itemsPerPage": 1},
                timeout=10,
            )
            response.raise_for_status()
            return {"Project Read Only": True}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (401, 403):
                return {
                    "Project Read Only": "Authentication failed, check the API key pair and that it has Project Read Only access"
                }
            return {"Project Read Only": str(e)}
        except requests.exceptions.RequestException as e:
            return {"Project Read Only": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        alerts = []
        page_num = 1
        while True:
            try:
                response = requests.get(
                    self._alerts_url(),
                    auth=self._auth,
                    headers={"Accept": self.ATLAS_API_VERSION_HEADER},
                    params={"itemsPerPage": self.PAGE_SIZE, "pageNum": page_num},
                    timeout=30,
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                raise ProviderException(
                    f"Failed to get alerts from MongoDB Atlas: {e}"
                ) from e
            data = response.json()
            results = data.get("results", [])
            alerts.extend(self._format_alert(alert) for alert in results)
            if not results or page_num * self.PAGE_SIZE >= data.get("totalCount", 0):
                break
            page_num += 1
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # Webhook payloads use the same schema as the Admin API alert resource,
        # so this formatter serves both the pull and push paths. Atlas does not
        # include a severity, only a status.
        status = MongodbatlasProvider.STATUS_MAP.get(
            event.get("status"), AlertStatus.FIRING
        )
        if event.get("acknowledgedUntil") and status == AlertStatus.FIRING:
            status = AlertStatus.ACKNOWLEDGED
        current_value = event.get("currentValue") or {}
        return AlertDto(
            id=event.get("id"),
            name=event.get("eventTypeName", "MongoDB Atlas alert"),
            status=status,
            severity=AlertSeverity.WARNING,
            lastReceived=event.get("updated")
            or event.get("created")
            or datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            description=event.get("humanReadable"),
            source=["mongodbatlas"],
            cluster=event.get("clusterName"),
            replicaSet=event.get("replicaSetName"),
            host=event.get("hostnameAndPort"),
            metric=event.get("metricName"),
            currentValue=current_value.get("number"),
            currentValueUnits=current_value.get("units"),
            groupId=event.get("groupId"),
            alertConfigId=event.get("alertConfigId"),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        authentication={
            "api_public_key": os.environ.get("ATLAS_API_PUBLIC_KEY"),
            "api_private_key": os.environ.get("ATLAS_API_PRIVATE_KEY"),
            "group_id": os.environ.get("ATLAS_GROUP_ID"),
        }
    )
    provider = MongodbatlasProvider(
        context_manager=context_manager,
        provider_id="mongodbatlas",
        config=config,
    )
    print(provider.validate_scopes())
    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} alerts")
