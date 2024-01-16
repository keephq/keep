"""
Ilert Provider is a class that allows to create/close incidents in Ilert.
"""
import dataclasses
import enum
import json
import os

import pydantic
import requests

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

    def _notify(
        self,
        summary: str = "",
        status: IlertIncidentStatus = IlertIncidentStatus.INVESTIGATING,
        message: str = "",
        affectedServices: str | list = "[]",
        id: str = "0",
        **kwargs: dict,
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
            **kwargs,
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

    provider_config = {
        "authentication": {"ilert_token": api_key},
    }
    provider: IlertProvider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="ilert",
        provider_type="ilert",
        provider_config=provider_config,
    )
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
