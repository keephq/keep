"""
Grafana Provider is a class that allows to ingest/digest data from Grafana.
"""

import dataclasses
import datetime

import pydantic
import requests
from packaging.version import Version

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
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
    PROVIDER_DISPLAY_NAME = "Grafana"
    """Pull/Push alerts from Grafana."""

    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    KEEP_GRAFANA_WEBHOOK_INTEGRATION_NAME = "keep-grafana-webhook-integration"
    FINGERPRINT_FIELDS = ["fingerprint"]

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

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
    }

    # https://grafana.com/docs/grafana/latest/alerting/manage-notifications/view-state-health/#alert-instance-state
    STATUS_MAP = {
        "ok": AlertStatus.RESOLVED,
        "resolved": AlertStatus.RESOLVED,
        "normal": AlertStatus.RESOLVED,
        "paused": AlertStatus.SUPPRESSED,
        "alerting": AlertStatus.FIRING,
        "pending": AlertStatus.PENDING,
        "no_data": AlertStatus.PENDING,
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
        try:
            response = requests.get(
                permissions_api, headers=headers, timeout=5, verify=False
            ).json()
        except requests.exceptions.ConnectionError:
            self.logger.exception("Failed to connect to Grafana")
            validated_scopes = {
                scope.name: "Failed to connect to Grafana. Please check your host."
                for scope in self.PROVIDER_SCOPES
            }
            return validated_scopes
        except Exception:
            self.logger.exception("Failed to get permissions from Grafana")
            validated_scopes = {
                scope.name: "Failed to get permissions. Please check your token."
                for scope in self.PROVIDER_SCOPES
            }
            return validated_scopes
        validated_scopes = {}
        for scope in self.PROVIDER_SCOPES:
            if scope.name in response:
                validated_scopes[scope.name] = True
            else:
                validated_scopes[scope.name] = "Missing scope"
        return validated_scopes

    def get_alerts_configuration(self, alert_id: str | None = None):
        api = f"{self.authentication_config.host}/api/v1/provisioning/alert-rules"
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        response = requests.get(api, verify=False, headers=headers)
        if not response.ok:
            self.logger.warning(
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
        api = f"{self.authentication_config.host}/api/v1/provisioning/alert-rules"
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        response = requests.post(api, verify=False, json=alert, headers=headers)

        if not response.ok:
            response_json = response.json()
            self.logger.warning(
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
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        alerts = event.get("alerts", [])
        formatted_alerts = []
        for alert in alerts:
            labels = alert.get("labels", {})
            # map status and severity to Keep format:
            status = GrafanaProvider.STATUS_MAP.get(
                event.get("status"), AlertStatus.FIRING
            )
            severity = GrafanaProvider.SEVERITIES_MAP.get(
                labels.get("severity"), AlertSeverity.INFO
            )
            service = alert.get("service", "unknown")
            fingerprint = alert.get("fingerprint", alert.get("alertname", "") + service)
            environment = labels.get(
                "deployment_environment", labels.get("environment", "unknown")
            )
            alert_dto = AlertDto(
                id=alert.get("fingerprint"),
                fingerprint=fingerprint,
                name=event.get("title"),
                status=status,
                severity=severity,
                environment=environment,
                lastReceived=datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat(),
                description=alert.get("annotations", {}).get("summary", ""),
                source=["grafana"],
                labels=labels,
            )
            # enrich extra payload with labels
            for label in labels:
                if getattr(alert_dto, label, None) is None:
                    setattr(alert_dto, label, labels[label])
            formatted_alerts.append(alert_dto)
        return formatted_alerts

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        self.logger.info("Setting up webhook")
        webhook_name = (
            f"{GrafanaProvider.KEEP_GRAFANA_WEBHOOK_INTEGRATION_NAME}-{tenant_id}"
        )
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        contacts_api = (
            f"{self.authentication_config.host}/api/v1/provisioning/contact-points"
        )
        try:
            self.logger.info("Getting contact points")
            all_contact_points = requests.get(
                contacts_api, verify=False, headers=headers
            )
            all_contact_points.raise_for_status()
            all_contact_points = all_contact_points.json()
        except Exception:
            self.logger.exception("Failed to get contact points")
            raise
        # check if webhook already exists
        webhook_exists = [
            webhook_exists
            for webhook_exists in all_contact_points
            if webhook_exists.get("name") == webhook_name
            or webhook_exists.get("uid") == webhook_name
        ]
        # grafana version lesser then 9.4.7 do not send their authentication correctly
        # therefor we need to add the api_key as a query param instead of the normal digest token
        self.logger.info("Getting Grafana version")
        try:
            health_api = f"{self.authentication_config.host}/api/health"
            health_response = requests.get(
                health_api, verify=False, headers=headers
            ).json()
            grafana_version = health_response["version"]
        except Exception:
            self.logger.exception("Failed to get Grafana version")
            raise
        self.logger.info(f"Grafana version is {grafana_version}")
        # if grafana version is greater then 9.4.7 we can use the digest token
        if Version(grafana_version) > Version("9.4.7"):
            self.logger.info("Installing Grafana version > 9.4.7")
            if webhook_exists:
                webhook = webhook_exists[0]
                webhook["settings"]["url"] = keep_api_url
                webhook["settings"]["authorization_scheme"] = "digest"
                webhook["settings"]["authorization_credentials"] = api_key
                requests.put(
                    f'{contacts_api}/{webhook["uid"]}',
                    verify=False,
                    json=webhook,
                    headers=headers,
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
                    verify=False,
                    json=webhook,
                    headers={**headers, "X-Disable-Provenance": "true"},
                )
                if not response.ok:
                    raise Exception(response.json())
                self.logger.info(f"Created webhook {webhook_name}")
        # if grafana version is lesser then 9.4.7 we need to add the api_key as a query param
        else:
            self.logger.info("Installing Grafana version < 9.4.7")
            if webhook_exists:
                webhook = webhook_exists[0]
                webhook["settings"]["url"] = f"{keep_api_url}&api_key={api_key}"
                requests.put(
                    f'{contacts_api}/{webhook["uid"]}',
                    verify=False,
                    json=webhook,
                    headers=headers,
                )
                self.logger.info(f'Updated webhook {webhook["uid"]}')
            else:
                self.logger.info('Creating webhook with name "{webhook_name}"')
                webhook = {
                    "name": webhook_name,
                    "type": "webhook",
                    "settings": {
                        "httpMethod": "POST",
                        "url": f"{keep_api_url}?api_key={api_key}",
                    },
                }
                response = requests.post(
                    contacts_api,
                    verify=False,
                    json=webhook,
                    headers={**headers, "X-Disable-Provenance": "true"},
                )
                if not response.ok:
                    raise Exception(response.json())
                self.logger.info(f"Created webhook {webhook_name}")
        # Finally, we need to update the policies to match the webhook
        if setup_alerts:
            self.logger.info("Setting up alerts")
            policies_api = (
                f"{self.authentication_config.host}/api/v1/provisioning/policies"
            )
            all_policies = requests.get(
                policies_api, verify=False, headers=headers
            ).json()
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
                        if "routes" not in all_policies:
                            all_policies["routes"] = []
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
                    verify=False,
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
                        status = alert.get("state", rule.get("state"))
                        status = GrafanaProvider.STATUS_MAP.get(
                            status, AlertStatus.FIRING
                        )
                        alert_dto = AlertDto(
                            id=alert_id,
                            name=rule.get("name"),
                            description=description,
                            status=status,
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

    def _get_alerts(self) -> list[AlertDto]:
        week_ago = int(
            (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
        )
        now = int(datetime.datetime.now().timestamp())
        api_endpoint = f"{self.authentication_config.host}/api/v1/rules/history?from={week_ago}&to={now}&limit=0"
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        response = requests.get(api_endpoint, verify=False, headers=headers, timeout=3)
        if not response.ok:
            raise ProviderException("Failed to get alerts from Grafana")
        events_history = response.json()
        events_data = events_history.get("data", [])
        if events_data:
            events_data_values = events_data.get("values")
            if events_data_values:
                events = events_data_values[1]
                events_time = events_data_values[0]
                alerts = []
                for i in range(0, len(events)):
                    event = events[i]
                    event_labels = event.get("labels", {})
                    alert_name = event_labels.get("alertname")
                    alert_status = event_labels.get("alertstate", event.get("current"))
                    alert_status = GrafanaProvider.STATUS_MAP.get(
                        alert_status, AlertStatus.FIRING
                    )
                    alert_severity = event_labels.get("severity")
                    alert_severity = GrafanaProvider.SEVERITIES_MAP.get(
                        alert_severity, AlertSeverity.INFO
                    )
                    environment = event_labels.get("environment", "unknown")
                    fingerprint = event_labels.get("fingerprint")
                    description = event.get("error", "")
                    rule_id = event.get("ruleUID")
                    condition = event.get("condition")
                    timestamp = datetime.datetime.fromtimestamp(
                        events_time[i] / 1000
                    ).isoformat()
                    alerts.append(
                        AlertDto(
                            id=str(i),
                            fingerprint=fingerprint,
                            name=alert_name,
                            status=alert_status,
                            severity=alert_severity,
                            environment=environment,
                            description=description,
                            lastReceived=timestamp,
                            rule_id=rule_id,
                            condition=condition,
                            labels=event_labels,
                            source=["grafana"],
                        )
                    )
                return alerts
        return []

    @classmethod
    def simulate_alert(cls, **kwargs) -> dict:
        import hashlib
        import json
        import random

        from keep.providers.grafana_provider.alerts_mock import ALERTS

        alert_type = kwargs.get("alert_type")
        if not alert_type:
            alert_type = random.choice(list(ALERTS.keys()))

        if "payload" in ALERTS[alert_type]:
            alert_payload = ALERTS[alert_type]["payload"]
        else:
            alert_payload = ALERTS[alert_type]["alerts"][0]
        alert_parameters = ALERTS[alert_type].get("parameters", {})
        # Generate random data for parameters
        for parameter, parameter_options in alert_parameters.items():
            if "." in parameter:
                parameter = parameter.split(".")
                if parameter[0] not in alert_payload:
                    alert_payload[parameter[0]] = {}
                alert_payload[parameter[0]][parameter[1]] = random.choice(
                    parameter_options
                )
            else:
                alert_payload[parameter] = random.choice(parameter_options)

        # Implement specific Grafana alert structure here
        # For example:
        alert_payload["state"] = AlertStatus.FIRING.value
        alert_payload["evalMatches"] = [
            {
                "value": random.randint(0, 100),
                "metric": "some_metric",
                "tags": alert_payload.get("labels", {}),
            }
        ]

        # Generate fingerprint
        fingerprint_src = json.dumps(alert_payload, sort_keys=True)
        fingerprint = hashlib.md5(fingerprint_src.encode()).hexdigest()
        alert_payload["fingerprint"] = fingerprint

        return {
            "alerts": [alert_payload],
            "severity": alert_payload.get("labels", {}).get("severity"),
            "title": "Grafana Alert - {}".format(alert_type),
        }


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
    alerts = provider.setup_webhook("test", "http://localhost:8000", "1234", True)
    print(alerts)
