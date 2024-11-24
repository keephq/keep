"""
Kibana provider.
"""

import dataclasses
import datetime
import json
import uuid
from typing import Literal
from urllib.parse import urlparse

import pydantic
import requests
from fastapi import HTTPException

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory
from keep.validation.fields import UrlPort


@pydantic.dataclasses.dataclass
class KibanaProviderAuthConfig:
    """Kibana authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Kibana API Key",
            "sensitive": True,
        }
    )
    kibana_host: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Kibana Host",
            "hint": "https://keep.kb.us-central1.gcp.cloud.es.io",
            "validation": "any_http_url"
        }
    )
    kibana_port: UrlPort = dataclasses.field(
        metadata={
            "required": False,
            "description": "Kibana Port (defaults to 9243)",
            "validation": "port"
        },
        default=9243,
    )


class KibanaProvider(BaseProvider):
    """Enrich alerts with data from Kibana."""

    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    DEFAULT_TIMEOUT = 10
    WEBHOOK_PAYLOAD = json.dumps(
        {
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
    )

    # Mock payloads for validating scopes
    MOCK_ALERT_PAYLOAD = {
        "name": "keep-test-alert",
        "schedule": {"interval": "1m"},
        "rule_type_id": "observability.rules.custom_threshold",
        "consumer": "logs",
        "enabled": False,
        "params": {
            "criteria": [],
            "searchConfiguration": {
                "query": {"query": "*", "language": "kuery"},
                "index": "",
            },
        },
    }
    MOCK_CONNECTOR_PAYLOAD = {
        "name": "keep-test-connector",
        "config": {
            "hasAuth": False,
            "method": "post",
            "url": "https://api.keephq.dev",
            "authType": False,
            "headers": {},
        },
        "secrets": {},
        "connector_type_id": ".webhook",
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="rulesSettings:read",
            description="Read alerts",
            mandatory=True,
            alias="Read Alerts",
        ),
        ProviderScope(
            name="rulesSettings:write",
            description="Modify alerts",
            mandatory=True,
            alias="Modify Alerts",
        ),
        ProviderScope(
            name="actions:read",
            description="Read connectors",
            mandatory=True,
            alias="Read Connectors",
        ),
        ProviderScope(
            name="actions:write",
            description="Write connectors",
            mandatory=True,
            alias="Write Connectors",
        ),
    ]

    SEVERITIES_MAP = {}

    STATUS_MAP = {
        "active": AlertStatus.FIRING,
        "Alert": AlertStatus.FIRING,
        "recovered": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    @staticmethod
    def parse_event_raw_body(raw_body: bytes | dict) -> dict:
        # tb: this is a f**king stupid hack because Kibana doesn't escape {{#toJson}} :(
        if b'"payload": "{' in raw_body:
            raw_body = raw_body.replace(b'"payload": "{', b'"payload": {')
            raw_body = raw_body.replace(b'}",', b"},")
        return json.loads(raw_body)

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.

        Returns:
            dict[str, bool | str]: A dictionary of scopes and whether they are valid or not
        """
        validated_scopes = {}
        for scope in self.PROVIDER_SCOPES:
            try:
                if scope.name == "rulesSettings:read":
                    self.request(
                        "GET", "api/alerting/rules/_find", params={"per_page": 1}
                    )
                elif scope.name == "rulesSettings:write":
                    alert = self.request(
                        "POST", "api/alerting/rule", json=self.MOCK_ALERT_PAYLOAD
                    )
                    self.request("DELETE", f"api/alerting/rule/{alert['id']}")
                elif scope.name == "actions:read":
                    self.request("GET", "api/actions/connectors")
                elif scope.name == "actions:write":
                    connector = self.request(
                        "POST",
                        "api/actions/connector",
                        json=self.MOCK_CONNECTOR_PAYLOAD,
                    )
                    self.request("DELETE", f"api/actions/connector/{connector['id']}")
            except HTTPException as e:
                if e.status_code == 403 or e.status_code == 401:
                    validated_scopes[scope.name] = e.detail
                # this means we faild on something else which is not permissions and it's probably ok.
                pass
            except Exception as e:
                validated_scopes[scope.name] = str(e)
                continue
            validated_scopes[scope.name] = True
        return validated_scopes

    def request(
        self, method: Literal["GET", "POST", "PUT", "DELETE"], uri: str, **kwargs
    ) -> dict:
        """
        Make a request to Kibana. Adds the API key to the headers.


        Args:
            method (POST|GET|PUT|DELETE): The HTTP method
            uri (str): The URI to request. This is relative to the Kibana host. (e.g. api/actions/connector)

        Raises:
            HTTPException: If the request fails

        Returns:
            dict: The response JSON
        """
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"ApiKey {self.authentication_config.api_key}"
        headers["kbn-xsrf"] = "reporting"
        response: requests.Response = getattr(requests, method.lower())(
            f"{self.authentication_config.kibana_host}:{self.authentication_config.kibana_port}/{uri}",
            headers=headers,
            **kwargs,
        )
        if not response.ok:
            response_json: dict = response.json()
            raise HTTPException(
                response_json.get("statusCode", 404),
                detail=response_json.get("message"),
            )
        try:
            return response.json()
        except requests.JSONDecodeError:
            return {}

    def __setup_webhook_alerts(self, tenant_id: str, keep_api_url: str, api_key: str):
        """
        Setup the webhook alerts for Kibana Alerting.

        Args:
            tenant_id (str): The tenant ID
            keep_api_url (str): The URL of the Keep API
            api_key (str): The API key of the Keep API
        """
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
        alert_rules = self.request(
            "GET",
            "api/alerting/rules/_find",
            params={"per_page": 1000},  # TODO: pagination
        )
        for alert_rule in alert_rules.get("data", []):
            self.logger.info(f"Updating alert {alert_rule['id']}")
            alert_actions = alert_rule.get("actions") or []
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
                self.logger.info(f"Alert {alert_rule['id']} already updated, skipping")
                continue
            for status in ["Alert", "Recovered", "No Data"]:
                alert_actions.append(
                    {
                        "group": (
                            "custom_threshold.fired"
                            if status == "Alert"
                            else (
                                "recovered"
                                if status == "Recovered"
                                else "custom_threshold.nodata"
                            )
                        ),
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
                    f"api/alerting/rule/{alert_rule['id']}",
                    json={
                        "actions": alert_actions,
                        "name": alert_rule["name"],
                        "tags": alert_rule["tags"],
                        "schedule": alert_rule["schedule"],
                        "params": alert_rule["params"],
                    },
                )
                self.logger.info(f"Updated alert {alert_rule['id']}")
            except HTTPException as e:
                self.logger.warning(
                    f"Failed to update alert {alert_rule['id']}",
                    extra={"error": e.detail},
                )
        self.logger.info("Done updating alerts")

    def __setup_watcher_alerts(self, tenant_id: str, keep_api_url: str, api_key: str):
        """
        Setup the webhook alerts for Kibana Watcher.

        Args:
            tenant_id (str): The tenant ID
            keep_api_url (str): The URL of the Keep API
            api_key (str): The API key of the Keep API
        """
        parsed_keep_url = urlparse(keep_api_url)
        keep_host = parsed_keep_url.netloc
        keep_port = 80 if "localhost" in keep_host else 443
        self.logger.info("Getting and updating all watches")
        watches = self.request(
            "POST", "api/console/proxy?path=%2F_watcher%2F_query%2Fwatches&method=GET"
        )
        for watch in watches.get("watches", []):
            watch_id = watch.get("_id")
            self.logger.info(f"Handling watch with id {watch_id}")
            watch = self.request(
                "POST",
                f"api/console/proxy?path=%2F_watcher%2Fwatch%2F{watch_id}&method=GET",
            ).get("watch")
            actions = watch.get("actions", {})
            actions[f"keep-{tenant_id}"] = {
                "webhook": {
                    "scheme": "https" if keep_port == 443 else "http",
                    "host": keep_host,
                    "port": keep_port,
                    "method": "post",
                    "path": f"{parsed_keep_url.path}",
                    "params": {},
                    "headers": {},
                    "auth": {"basic": {"username": "keep", "password": api_key}},
                    "body": '{"payload": "{{#toJson}}ctx{{/toJson}}", "status": "Alert"}',
                }
            }
            self.request(
                "POST",
                f"api/console/proxy?path=%2F_watcher%2Fwatch%2F{watch_id}&method=PUT",
                json={**watch},
            )
            self.logger.info(f"Finished handling watch with id {watch_id}")
        self.logger.info("Done getting and updating all watches")

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        """
        Setup the webhook for Kibana.

        Args:
            tenant_id (str): The tenant ID
            keep_api_url (str): The URL of the Keep API
            api_key (str): The API key of the Keep API
            setup_alerts (bool, optional): Whether to setup alerts or not. Defaults to True.
        """
        self.logger.info("Setting up webhooks")

        self.logger.info("Setting up Kibana Alerting webhook alerts")
        try:
            self.__setup_webhook_alerts(tenant_id, keep_api_url, api_key)
            self.logger.info("Done setting up Kibana Alerting webhook alerts")
        except Exception as e:
            self.logger.warning(
                "Failed to setup Kibana Alerting webhook alerts",
                extra={"error": str(e)},
            )

        self.logger.info("Setting up Kibana Watcher webhook alerts")
        try:
            self.__setup_watcher_alerts(tenant_id, keep_api_url, api_key)
            self.logger.info("Done setting up Kibana Watcher webhook alerts")
        except Exception as e:
            self.logger.warning(
                "Failed to setup Kibana Watcher webhook alerts",
                extra={"error": str(e)},
            )

        self.logger.info("Done setting up webhooks")

    def validate_config(self):
        if self.is_installed or self.is_provisioned:
            host = self.config.authentication['kibana_host']
            if not (host.startswith("http://") or host.startswith("https://")):
                scheme = "http://" if "localhost" in host else "https://"
                self.config.authentication['kibana_host'] = scheme + host

        self.authentication_config = KibanaProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        # no need to dipose anything
        pass

    @staticmethod
    def format_alert_from_watcher(event: dict) -> AlertDto | list[AlertDto]:
        payload = event.get("payload", {})
        alert_id = payload.pop("id")
        alert_metadata = payload.get("metadata", {})
        alert_name = alert_metadata.get("name") if alert_metadata else alert_id
        last_received = payload.get("trigger", {}).get(
            "triggered_time",
            datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        )
        # map status to keep status
        status = KibanaProvider.STATUS_MAP.get(
            event.pop("status", None), AlertStatus.FIRING
        )
        # kibana watcher doesn't have severity, so we'll use default (INFO)
        severity = AlertSeverity.INFO

        return AlertDto(
            id=alert_id,
            name=alert_name,
            fingerprint=payload.get("watch_id", alert_id),
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["kibana"],
            **event,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Formats an alert from Kibana to a standard format.

        Args:
            event (dict): The event from Kibana

        Returns:
            AlertDto | list[AlertDto]: The alert in a standard format
        """

        # If this is coming from Kibana Watcher
        if "payload" in event:
            return KibanaProvider.format_alert_from_watcher(event)
        try:
            labels = {
                v.split("=", 1)[0]: v.split("=", 1)[1]
                for v in event.get("ruleTags", "").split(",")
            }
        except Exception:
            # Failed to extract labels from ruleTags
            labels = {}

        try:
            labels.update(
                {
                    v.split("=", 1)[0]: v.split("=", 1)[1]
                    for v in event.get("contextTags", "").split(",")
                }
            )
        except Exception:
            # Failed to enrich labels with contextTags
            pass

        environment = labels.get("environment", "undefined")

        # format status and severity to Keep format
        event["status"] = KibanaProvider.STATUS_MAP.get(
            event.get("status"), AlertStatus.FIRING
        )
        event["severity"] = KibanaProvider.SEVERITIES_MAP.get(
            event.get("severity"), AlertSeverity.INFO
        )
        return AlertDto(
            environment=environment, labels=labels, source=["kibana"], **event
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
    result = provider.validate_scopes()
    print(result)
