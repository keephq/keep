"""
Grafana Provider is a class that allows to ingest/digest data from Grafana.
"""

import dataclasses
import datetime
import random

import pydantic
import requests
from grafana_api.model import APIEndpoints

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.base.provider_exceptions import GetAlertException
from keep.providers.grafana_provider.grafana_alert_format_description import (
    GrafanaAlertFormatDescription,
)
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class GrafanaProviderAuthConfig:
    """
    Grafana authentication configuration.
    """

    token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Token",
            "hint": "Grafana Token",
            "sensitive": True,
        },
    )
    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Grafana host",
            "hint": "e.g. https://keephq.grafana.net",
        },
    )


class GrafanaProvider(BaseProvider):
    """Pull/Push alerts from Grafana."""

    KEEP_GRAFANA_WEBHOOK_INTEGRATION_NAME = "keep-grafana-webhook-integration"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="alert.rules:read",
            description="Read Grafana alert rules in a folder and its subfolders.",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://grafana.com/docs/grafana/latest/administration/roles-and-permissions/access-control/custom-role-actions-scopes/",
            alias="Rules Reader",
        ),
        ProviderScope(
            name="alert.provisioning:read",
            description="Read all Grafana alert rules, notification policies, etc via provisioning API.",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://grafana.com/docs/grafana/latest/administration/roles-and-permissions/access-control/custom-role-actions-scopes/",
            alias="Access to alert rules provisioning API",
        ),
        ProviderScope(
            name="alert.provisioning:write",
            description="Update all Grafana alert rules, notification policies, etc via provisioning API.",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://grafana.com/docs/grafana/latest/administration/roles-and-permissions/access-control/custom-role-actions-scopes/",
            alias="Access to alert rules provisioning API",
        ),
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
        Validates required configuration for Grafana provider.

        """
        self.authentication_config = GrafanaProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.host.startswith(
            "https://"
        ) and not self.authentication_config.host.startswith("http://"):
            self.authentication_config.host = (
                f"https://{self.authentication_config.host}"
            )

    def validate_scopes(self) -> dict[str, bool | str]:
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        permissions_api = (
            f"{self.authentication_config.host}/api/access-control/user/permissions"
        )
        response = requests.get(permissions_api, headers=headers).json()
        validated_scopes = {}
        for scope in self.PROVIDER_SCOPES:
            if scope.name in response:
                validated_scopes[scope.name] = True
            else:
                validated_scopes[scope.name] = "Missing scope"
        return validated_scopes

    def get_alerts_configuration(self, alert_id: str | None = None):
        api = f"{self.authentication_config.host}{APIEndpoints.ALERTING_PROVISIONING.value}/alert-rules"
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        response = requests.get(api, headers=headers)
        if not response.ok:
            self.logger.warn(
                "Could not get alerts", extra={"response": response.json()}
            )
            error = response.json()
            if response.status_code == 403:
                error[
                    "message"
                ] += f"\nYou can test your permissions with \n\tcurl -H 'Authorization: Bearer {{token}}' -X GET '{self.authentication_config.host}/api/access-control/user/permissions' | jq \nDocs: https://grafana.com/docs/grafana/latest/administration/service-accounts/#debug-the-permissions-of-a-service-account-token"
            raise GetAlertException(message=error, status_code=response.status_code)
        return response.json()

    def deploy_alert(self, alert: dict, alert_id: str | None = None):
        self.logger.info("Deploying alert")
        api = f"{self.authentication_config.host}{APIEndpoints.ALERTING_PROVISIONING.value}/alert-rules"
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        response = requests.post(api, json=alert, headers=headers)

        if not response.ok:
            response_json = response.json()
            self.logger.warn(
                "Could not deploy alert", extra={"response": response_json}
            )
            raise Exception(response_json)

        self.logger.info(
            "Alert deployed",
            extra={
                "response": response.json(),
                "status": response.status_code,
            },
        )

    @staticmethod
    def get_alert_schema():
        return GrafanaAlertFormatDescription.schema()

    @staticmethod
    def format_alert(event: dict) -> AlertDto:
        alert = event.get("alerts", [{}])[0]
        return AlertDto(
            id=alert.get("fingerprint"),
            name=event.get("title"),
            status=event.get("status"),
            severity=alert.get("severity", None),
            lastReceived=datetime.datetime.utcnow().isoformat(),
            fatigueMeter=random.randint(0, 100),
            description=alert.get("annotations", {}).get("summary", ""),
            source=["grafana"],
            **alert.get("labels", {}),
        )

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        self.logger.info("Setting up webhook")
        webhook_name = (
            f"{GrafanaProvider.KEEP_GRAFANA_WEBHOOK_INTEGRATION_NAME}-{tenant_id}"
        )
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        contacts_api = f"{self.authentication_config.host}{APIEndpoints.ALERTING_PROVISIONING.value}/contact-points"
        all_contact_points = requests.get(contacts_api, headers=headers)
        all_contact_points.raise_for_status()
        all_contact_points = all_contact_points.json()
        webhook_exists = [
            webhook_exists
            for webhook_exists in all_contact_points
            if webhook_exists.get("name") == webhook_name
            or webhook_exists.get("uid") == webhook_name
        ]
        if webhook_exists:
            webhook = webhook_exists[0]
            webhook["settings"]["url"] = keep_api_url
            webhook["settings"]["authorization_scheme"] = "digest"
            webhook["settings"]["authorization_credentials"] = api_key
            requests.put(
                f'{contacts_api}/{webhook["uid"]}', json=webhook, headers=headers
            )
            self.logger.info(f'Updated webhook {webhook["uid"]}')
        else:
            self.logger.info('Creating webhook with name "{webhook_name}"')
            webhook = {
                "name": webhook_name,
                "type": "webhook",
                "settings": {
                    "httpMethod": "POST",
                    "url": keep_api_url,
                    "authorization_scheme": "digest",
                    "authorization_credentials": api_key,
                },
            }
            response = requests.post(
                contacts_api,
                json=webhook,
                headers={**headers, "X-Disable-Provenance": "true"},
            )
            if not response.ok:
                raise Exception(response.json())
            self.logger.info(f"Created webhook {webhook_name}")
        if setup_alerts:
            self.logger.info("Setting up alerts")
            policies_api = f"{self.authentication_config.host}{APIEndpoints.ALERTING_PROVISIONING.value}/policies"
            all_policies = requests.get(policies_api, headers=headers).json()
            policy_exists = any(
                [
                    p
                    for p in all_policies.get("routes", [])
                    if p.get("receiver") == webhook_name
                ]
            )
            if not policy_exists:
                if all_policies["receiver"]:
                    default_policy = {
                        "receiver": all_policies["receiver"],
                        "continue": True,
                    }
                    if not any(
                        [
                            p
                            for p in all_policies.get("routes", [])
                            if p == default_policy
                        ]
                    ):
                        # This is so we won't override the default receiver if customer has one.
                        all_policies["routes"].append(
                            {"receiver": all_policies["receiver"], "continue": True}
                        )
                all_policies["routes"].append(
                    {
                        "receiver": webhook_name,
                        "continue": True,
                    }
                )
                requests.put(
                    policies_api,
                    json=all_policies,
                    headers={**headers, "X-Disable-Provenance": "true"},
                )
                self.logger.info("Updated policices to match alerts to webhook")
            else:
                self.logger.info("Policies already match alerts to webhook")
        self.logger.info("Webhook successfuly setup")

    def __extract_rules(self, alerts: dict, source: list) -> list[AlertDto]:
        alert_ids = []
        alert_dtos = []
        for group in alerts.get("data", {}).get("groups", []):
            for rule in group.get("rules", []):
                for alert in rule.get("alerts", []):
                    alert_id = rule.get(
                        "id", rule.get("name", "").replace(" ", "_").lower()
                    )

                    if alert_id in alert_ids:
                        # de duplicate alerts
                        continue

                    description = alert.get("annotations", {}).pop(
                        "description", None
                    ) or alert.get("annotations", {}).get("summary", rule.get("name"))

                    labels = {k.lower(): v for k, v in alert.get("labels", {}).items()}
                    annotations = {
                        k.lower(): v for k, v in alert.get("annotations", {}).items()
                    }
                    try:
                        alert_dto = AlertDto(
                            id=alert_id,
                            name=rule.get("name"),
                            description=description,
                            status=alert.get("state", rule.get("state")),
                            lastReceived=alert.get("activeAt"),
                            source=source,
                            **labels,
                            **annotations,
                        )
                        alert_ids.append(alert_id)
                        alert_dtos.append(alert_dto)
                    except Exception:
                        self.logger.warning(
                            "Failed to parse alert",
                            extra={
                                "alert_id": alert_id,
                                "alert_name": rule.get("name"),
                            },
                        )
                        continue
        return alert_dtos

    def get_alerts(self) -> list[AlertDto]:
        source_by_api_url = {
            f"{self.authentication_config.host}/api/prometheus/grafana/api/v1/rules": [
                "grafana"
            ],
            f"{self.authentication_config.host}/api/prometheus/grafanacloud-prom/api/v1/rules": [
                "grafana",
                "prometheus",
            ],
        }
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        alert_dtos = []
        for url in source_by_api_url:
            try:
                response = requests.get(url, headers=headers)
                if not response.ok:
                    continue
                rules = response.json()
                alert_dtos.extend(self.__extract_rules(rules, source_by_api_url[url]))
            except Exception:
                self.logger.exception("Could not get alerts", extra={"api": url})
        return alert_dtos


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    host = os.environ.get("GRAFANA_HOST")
    token = os.environ.get("GRAFANA_TOKEN")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = {
        "authentication": {"host": host, "token": token},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="grafana-keephq",
        provider_type="grafana",
        provider_config=config,
    )
    alerts = provider.setup_webhook("http://localhost:8000", "1234", True)
    print(alerts)
