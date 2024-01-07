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
from keep.providers.models.provider_config import ProviderConfig
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

    PROVIDER_SCOPES = []

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

    # def validate_scopes(self):
    #     scopes = {}
    #     self.logger.info("Validating scopes")
    #     # TBD
    #         for scope in self.PROVIDER_SCOPES:
    #             try:
    #                 if scope.name == "monitors_read":
    #                     api = MonitorsApi(api_client)
    #                     api.list_monitors()
    #                 elif scope.name == "monitors_write":
    #                     api = MonitorsApi(api_client)
    #                     body = Monitor(
    #                         name="Example-Monitor",
    #                         type=MonitorType.RUM_ALERT,
    #                         query='formula("1 * 100").last("15m") >= 200',
    #                         message="some message Notify: @hipchat-channel",
    #                         tags=[
    #                             "test:examplemonitor",
    #                             "env:ci",
    #                         ],
    #                         priority=3,
    #                         options=MonitorOptions(
    #                             thresholds=MonitorThresholds(
    #                                 critical=200,
    #                             ),
    #                             variables=[],
    #                         ),
    #                     )
    #                     monitor = api.create_monitor(body)
    #                     api.delete_monitor(monitor.id)
    #                 elif scope.name == "create_webhooks":
    #                     api = WebhooksIntegrationApi(api_client)
    #                     # We check if we have permissions to query webhooks, this means we have the create_webhooks scope
    #                     try:
    #                         api.create_webhooks_integration(
    #                             body={
    #                                 "name": "keep-webhook-scope-validation",
    #                                 "url": "https://example.com",
    #                             }
    #                         )
    #                         # for some reason create_webhooks does not allow to delete: api.delete_webhooks_integration(webhook_name), no scope for deletion
    #                     except ApiException as e:
    #                         # If it's something different from 403 it means we have access! (for example, already exists because we created it once)
    #                         if e.status == 403:
    #                             raise e
    #                 elif scope.name == "metrics_read":
    #                     api = MetricsApi(api_client)
    #                     api.query_metrics(
    #                         query="system.cpu.idle{*}",
    #                         _from=int((datetime.datetime.now()).timestamp()),
    #                         to=int(datetime.datetime.now().timestamp()),
    #                     )
    #                 elif scope.name == "logs_read":
    #                     self._query(
    #                         query="*",
    #                         timeframe="1h",
    #                         query_type="logs",
    #                     )
    #                 elif scope.name == "events_read":
    #                     api = EventsApi(api_client)
    #                     end = datetime.datetime.now()
    #                     start = datetime.datetime.now() - datetime.timedelta(hours=1)
    #                     api.list_events(
    #                         start=int(start.timestamp()), end=int(end.timestamp())
    #                     )
    #             except ApiException as e:
    #                 # API failed and it means we're probably lacking some permissions
    #                 # perhaps we should check if status code is 403 and otherwise mark as valid?
    #                 self.logger.warning(
    #                     f"Failed to validate scope {scope.name}",
    #                     extra={"reason": e.reason, "code": e.status},
    #                 )
    #                 scopes[scope.name] = str(e.reason)
    #                 continue
    #             scopes[scope.name] = True
    #     self.logger.info("Scopes validated", extra=scopes)
    #     return scopes

    def _query(
        self,
        summary: str,
        status: IlertIncidentStatus = IlertIncidentStatus.INVESTIGATING,
        message: str = "",
        affectedServices: str = "[]",
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
            "summary": summary,
            "status": str(status),
            "message": message,
            **kwargs,
        }
        if affectedServices:
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

        # if id is set, we update the incident, otherwise we create a new one
        should_update = id and id != "0"
        if not should_update:
            response = requests.post(
                f"{self.authentication_config.ilert_host}/incidents",
                headers=headers,
                json=payload,
            )
        else:
            response = requests.put(
                f"{self.authentication_config.ilert_host}/incidents/{id}",
                headers=headers,
                json=payload,
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
