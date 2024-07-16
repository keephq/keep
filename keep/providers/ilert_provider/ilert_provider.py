"""
Ilert Provider is a class that allows to create/close incidents in Ilert.
"""

import dataclasses
import enum
import json
import os
from typing import Literal

import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


class IlertIncidentStatus(str, enum.Enum):
    """
    Ilert incident status.
    """

    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    MONITORING = "MONITORING"
    IDENTIFIED = "IDENTIFIED"


class IlertServiceStatus(str, enum.Enum):
    """
    Ilert service status.
    """

    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    PARTIAL_OUTAGE = "PARTIAL_OUTAGE"
    MAJOR_OUTAGE = "MAJOR_OUTAGE"
    UNDER_MAINTENANCE = "UNDER_MAINTENANCE"


class IlertServiceNoIncludes(pydantic.BaseModel):
    """
    Ilert service.
    """

    id: str


class IlertAffectedService(pydantic.BaseModel):
    """
    Ilert affected service.
    """

    service: IlertServiceNoIncludes
    impact: IlertServiceStatus


@pydantic.dataclasses.dataclass
class IlertProviderAuthConfig:
    """
    Ilert authentication configuration.
    """

    ilert_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "ILert API token",
            "hint": "Bearer eyJhbGc...",
            "sensitive": True,
        }
    )
    ilert_host: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "ILert API host",
            "hint": "https://api.ilert.com/api",
        },
        default="https://api.ilert.com/api",
    )


class IlertProvider(BaseProvider):
    """Create/Resolve incidents in Ilert."""

    PROVIDER_SCOPES = [
        ProviderScope("read_permission", "Read permission", mandatory=True),
        ProviderScope("write_permission", "Write permission", mandatory=False),
    ]

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
        Validates required configuration for Ilert provider.

        """
        self.authentication_config = IlertProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        scopes = {}
        self.logger.info("Validating scopes")
        for scope in self.PROVIDER_SCOPES:
            try:
                if scope.name == "read_permission":
                    requests.get(
                        f"{self.authentication_config.ilert_host}/incidents",
                        headers={
                            "Authorization": self.authentication_config.ilert_token
                        },
                    )
                    scopes[scope.name] = True
                elif scope.name == "write_permission":
                    # TODO: find a way to validate write_permissions, for now it is always "validated" sucessfully.
                    scopes[scope.name] = True
            except Exception as e:
                self.logger.warning(
                    "Failed to validate scope",
                    extra={"scope": scope.name},
                )
                scopes[scope.name] = str(e)
        self.logger.info("Scopes validated", extra=scopes)
        return scopes

    def _query(self, incident_id: str, **kwargs):
        """
        Query Ilert incident.
        """
        self.logger.info(
            "Querying Ilert incident",
            extra={
                "incident_id": incident_id,
                **kwargs,
            },
        )
        headers = {"Authorization": self.authentication_config.ilert_token}
        response = requests.get(
            f"{self.authentication_config.ilert_host}/incidents/{incident_id}",
            headers=headers,
        )
        if not response.ok:
            self.logger.error(
                "Failed to query Ilert incident",
                extra={
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            raise Exception(
                f"Failed to query Ilert incident: {response.status_code} {response.text}"
            )
        self.logger.info(
            "Ilert incident queried",
            extra={"status_code": response.status_code},
        )
        return response.json()

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get incidents from Ilert.
        """
        if not self.authentication_config.ilert_host.endswith("/api"):
            self.authentication_config.ilert_host = (
                f"{self.authentication_config.ilert_host}/api"
            )

        headers = {"Authorization": f"{self.authentication_config.ilert_token}"}
        response = requests.get(
            f"{self.authentication_config.ilert_host}/incidents",
            headers=headers,
        )
        if not response.ok:
            self.logger.error(
                "Failed to get alerts",
                extra={
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            raise Exception(
                f"Failed to get alerts: {response.status_code} {response.text}"
            )

        alerts = response.json()
        self.logger.info(
            "Got alerts from ilert", extra={"number_of_alerts": len(alerts)}
        )
        return [
            AlertDto(
                id=alert["id"],
                name=alert["summary"],
                title=alert["summary"],
                description=alert["message"],
                status=alert["status"],
                sendNotification=alert["sendNotification"],
                createdAt=alert["createdAt"],
                updatedAt=alert["updatedAt"],
                affectedServices=alert["affectedServices"],
                createdBy=alert["createdBy"],
                lastHistory=alert["lastHistory"],
                lastHistoryCreatedAt=alert["lastHistoryCreatedAt"],
                lastHistoryUpdatedAt=alert["lastHistoryUpdatedAt"],
                lastReceived=alert["updatedAt"],
            )
            for alert in alerts
        ]

    def __create_or_update_incident(
        self, summary, status, message, affectedServices, id
    ):
        self.logger.info(
            "Creating/updating Ilert incident",
            extra={
                "summary": summary,
                "status": status,
                "incident_message": message,
                "affectedServices": affectedServices,
                "id": id,
            },
        )
        headers = {"Authorization": self.authentication_config.ilert_token}

        # Create or update incident
        payload = {
            "id": id,
            "status": str(status),
            "message": message,
        }

        # if id is set, we update the incident, otherwise we create a new one
        should_update = id and id != "0"
        if not should_update:
            try:
                payload["affectedServices"] = (
                    json.loads(affectedServices)
                    if isinstance(affectedServices, str)
                    else affectedServices
                )
            except Exception:
                self.logger.warning(
                    "Failed to parse affectedServices",
                    extra={"affectedServices": affectedServices},
                )
                raise
            if not summary:
                raise Exception("summary is required")
            payload["summary"] = summary
            response = requests.post(
                f"{self.authentication_config.ilert_host}/incidents",
                headers=headers,
                json=payload,
            )
        else:
            incident = requests.get(
                f"{self.authentication_config.ilert_host}/incidents/{id}",
                headers=headers,
            ).json()
            response = requests.put(
                f"{self.authentication_config.ilert_host}/incidents/{id}",
                headers=headers,
                json={**incident, **payload},
            )

        if not response.ok:
            self.logger.error(
                "Failed to create/update Ilert incident",
                extra={
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            raise Exception(
                f"Failed to create/update Ilert incident: {response.status_code} {response.text}"
            )
        self.logger.info(
            "Ilert incident created/updated",
            extra={"status_code": response.status_code},
        )
        return response.json()

    def __post_ilert_event(
        self,
        event_type: Literal["ALERT", "ACCEPT", "RESOLVE"] = "ALERT",
        summary: str = "",
        details: str = "",
        alert_key: str = "",
        priority: Literal["HIGH", "LOW"] = "HIGH",
        images: list = [],
        links: list = [],
        custom_details: dict = {},
        routing_key: str = "",
    ):
        payload = {
            "eventType": event_type,
            "summary": summary,
            "details": details,
            "alertKey": alert_key,
            "priority": priority,
            "images": images,
            "links": links,
            "customDetails": custom_details,
            "routingKey": routing_key,
        }
        self.logger.info("Posting Ilert event", extra=payload)
        payload["apiKey"] = self.authentication_config.ilert_token
        response = requests.post(
            f"{self.authentication_config.ilert_host}/events",
            json=payload,
        )
        self.logger.info(
            "Ilert event posted", extra={"status_code": response.status_code}
        )
        return response.json()

    def _notify(
        self,
        _type: Literal["incident", "event"] = "event",
        summary: str = "",
        status: IlertIncidentStatus = IlertIncidentStatus.INVESTIGATING,
        message: str = "",
        affectedServices: str | list = "[]",
        id: str = "0",
        event_type: Literal["ALERT", "ACCEPT", "RESOLVE"] = "ALERT",
        details: str = "",
        alert_key: str = "",
        priority: Literal["HIGH", "LOW"] = "HIGH",
        images: list = [],
        links: list = [],
        custom_details: dict = {},
        routing_key: str = "",
        **kwargs: dict,
    ):
        self.logger.info("Notifying Ilert", extra=locals())
        if _type == "incident":
            return self.__create_or_update_incident(
                summary, status, message, affectedServices, id
            )
        else:
            return self.__post_ilert_event(
                event_type,
                summary,
                details,
                alert_key,
                priority,
                images,
                links,
                custom_details,
                routing_key,
            )


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    api_key = os.environ.get("ILERT_API_TOKEN")
    host = os.environ.get("ILERT_API_HOST")

    provider_config = {
        "authentication": {"ilert_token": api_key, "ilert_host": host},
    }
    provider: IlertProvider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="ilert",
        provider_type="ilert",
        provider_config=provider_config,
    )
    """
    result = provider._query(
        "Example",
        message="Lorem Ipsum",
        status="MONITORING",
        affectedServices=json.dumps(
            [
                {
                    "impact": "OPERATIONAL",
                    "service": {"id": 339743},
                }
            ]
        ),
        id="242530",
    )
    print(result)
    """
    alerts = provider._get_alerts()
    print(alerts)
