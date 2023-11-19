"""
Elasticsearch provider.
"""
import dataclasses
import uuid
from typing import Literal

import pydantic
import requests
from fastapi import HTTPException

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class KibanaProviderAuthConfig:
    """Elasticsearch authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Kibana API Key",
            "sensitive": True,
        }
    )
    kibana_host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Kibana Host (e.g. keep.kb.us-central1.gcp.cloud.es.io)",
        }
    )
    kibana_port: str = dataclasses.field(
        metadata={"required": False, "description": "Kibana Port (defaults to 9243)"},
        default="9243",
    )


class KibanaProvider(BaseProvider):
    """Enrich alerts with data from Elasticsearch."""

    DEFAULT_TIMEOUT = 10
    WEBHOOK_PAYLOAD = {
        "actionGroup": "{{alert.actionGroup}}",
        "status": "{{alert.actionGroupName}}",
        "actionSubgroup": "{{alert.actionSubgroup}}",
        "isFlapping": "{{alert.flapping}}",
        "id": "{{alert.id}}",
        "fingerprint": "{{alert.id}}",
        "url": "{{context.alertDetailsUrl}}",
        "context.cloud": "{{context.cloud}}",
        "context.container": "{{context.container}}",
        "context.group": "{{context.group}}",
        "context.host": "{{context.host}}",
        "context.labels": "{{context.labels}}",
        "context.orchestrator": "{{context.orchestrator}}",
        "description": "{{context.reason}}",
        "contextTags": "{{context.tags}}",
        "context.timestamp": "{{context.timestamp}}",
        "context.value": "{{context.value}}",
        "lastReceived": "{{date}}",
        "ruleId": "{{rule.id}}",
        "rule.spaceId": "{{rule.spaceId}}",
        "ruleUrl": "{{rule.url}}",
        "ruleTags": "{{rule.tags}}",
        "name": "{{rule.name}}",
        "rule.type": "{{rule.type}}",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def request(
        self, method: Literal["GET", "POST", "PUT", "DELETE"], uri: str, **kwargs
    ) -> dict:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"ApiKey {self.authentication_config.api_key}"
        headers["kbn-xsrf"] = "reporting"
        response: requests.Response = getattr(requests, method.lower())(
            f"https://{self.authentication_config.kibana_host}:{self.authentication_config.kibana_port}/{uri}",
            headers=headers,
            **kwargs,
        )
        if not response.ok:
            response_json: dict = response.json()
            raise HTTPException(
                response_json.get("statusCode", 404),
                detail=response_json.get("message"),
            )
        return response.json()

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        self.logger.info("Setting up webhook")
        # First get all existing connectors and check if we're already installed:
        connectors = self.request("GET", "api/actions/connectors")
        connector_name = f"keep-{tenant_id}"
        connector = next(
            iter(
                [
                    connector
                    for connector in connectors
                    if connector["name"] == connector_name
                ]
            ),
            None,
        )
        if connector:
            self.logger.info(
                "Connector already exists, updating",
                extra={"connector_id": connector["id"]},
            )
            # this means we already have a connector installed, so we just need to update it
            config: dict = connector["config"]
            config["url"] = keep_api_url
            config["headers"] = {"X-API-KEY": api_key}
            self.request(
                "PUT",
                f"api/actions/connector/{connector['id']}",
                json={
                    "config": config,
                    "name": connector_name,
                },
            )
        else:
            self.logger.info("Connector does not exist, creating")
            # we need to create a new connector
            body = {
                "name": connector_name,
                "config": {
                    "hasAuth": False,
                    "method": "post",
                    "url": keep_api_url,
                    "authType": None,
                    "headers": {"X-API-KEY": api_key},
                },
                "secrets": {},
                "connector_type_id": ".webhook",
            }
            connector = self.request("POST", "api/actions/connector", json=body)
            self.logger.info(
                "Connector created", extra={"connector_id": connector["id"]}
            )
        connector_id = connector["id"]

        # Now we need to update all the alerts and add actions that use this connector
        self.logger.info("Updating alerts")
        alerts = self.request(
            "GET",
            "api/alerting/rules/_find",
            params={"per_page": 1000},  # TODO: pagination
        )
        for alert in alerts.get("data", []):
            self.logger.info(f"Updating alert {alert['id']}")
            alert_actions = alert.get("actions") or []
            keep_action_exists = any(
                iter(
                    [
                        action
                        for action in alert_actions
                        if action.get("id") == connector_id
                    ]
                )
            )
            if keep_action_exists:
                # This alert was already modified by us / manually added
                self.logger.info(f"Alert {alert['id']} already updated, skipping")
                continue
            for status in ["Alert", "Recovered", "No Data"]:
                alert_actions.append(
                    {
                        "group": "custom_threshold.fired"
                        if status == "Alert"
                        else "recovered"
                        if status == "Recovered"
                        else "custom_threshold.nodata",
                        "id": connector_id,
                        "params": {"body": KibanaProvider.WEBHOOK_PAYLOAD},
                        "frequency": {
                            "notify_when": "onActionGroupChange",
                            "throttle": None,
                            "summary": False,
                        },
                        "uuid": str(uuid.uuid4()),
                    }
                )
            try:
                self.request(
                    "PUT",
                    f"api/alerting/rule/{alert['id']}",
                    json={
                        "actions": alert_actions,
                        "name": alert["name"],
                        "tags": alert["tags"],
                        "schedule": alert["schedule"],
                        "params": alert["params"],
                    },
                )
                self.logger.info(f"Updated alert {alert['id']}")
            except HTTPException as e:
                self.logger.warning(
                    f"Failed to update alert {alert['id']}", extra={"error": e.detail}
                )
        self.logger.info("Done updating alerts")
        self.logger.info("Done setting up webhook")

    def validate_config(self):
        self.authentication_config = KibanaProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        # no need to dipose anything
        pass

    @staticmethod
    def format_alert(event: dict) -> AlertDto | list[AlertDto]:
        labels = {
            v.split("=", 1)[0]: v.split("=", 1)[1]
            for v in event.get("ruleTags", "").split(",")
        }
        labels.update(
            {
                v.split("=", 1)[0]: v.split("=", 1)[1]
                for v in event.get("contextTags", "").split(",")
            }
        )
        environment = labels.get("environment", "undefined")
        return AlertDto(
            environment=environment, labels=labels, source=["elastic"], **event
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

    kibana_host = os.environ.get("KIBANA_HOST")
    api_key = os.environ.get("KIBANA_API_KEY")

    # Initalize the provider and provider config
    config = {
        "authentication": {
            "kibana_host": kibana_host,
            "api_key": api_key,
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="kibana",
        provider_type="kibana",
        provider_config=config,
    )
    result = provider.setup_webhook()
    print(result)
