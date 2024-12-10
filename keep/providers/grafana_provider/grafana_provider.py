"""
Grafana Provider is a class that allows to ingest/digest data from Grafana.
"""

import dataclasses
import datetime
import time

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
    host: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Grafana host",
            "hint": "e.g. https://keephq.grafana.net",
            "validation": "any_http_url",
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
        # Check if this is a legacy alert based on structure
        if "evalMatches" in event:
            return GrafanaProvider._format_legacy_alert(event)

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

    @staticmethod
    def _format_legacy_alert(event: dict) -> AlertDto:
        # Legacy alerts have a different structure
        status = (
            AlertStatus.FIRING
            if event.get("state") == "alerting"
            else AlertStatus.RESOLVED
        )
        severity = GrafanaProvider.SEVERITIES_MAP.get("critical", AlertSeverity.INFO)

        alert_dto = AlertDto(
            id=str(event.get("ruleId", "")),
            fingerprint=str(event.get("ruleId", "")),
            name=event.get("ruleName", ""),
            status=status,
            severity=severity,
            lastReceived=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            description=event.get("message", ""),
            source=["grafana"],
            labels={
                "metric": event.get("metric", ""),
                "ruleId": str(event.get("ruleId", "")),
                "ruleName": event.get("ruleName", ""),
                "ruleUrl": event.get("ruleUrl", ""),
                "state": event.get("state", ""),
            },
        )
        return [alert_dto]

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

        # After setting up unified alerting, check and setup legacy alerting if enabled
        try:
            if self._is_legacy_alerting_enabled():
                self._setup_legacy_alerting_webhook(
                    webhook_name, keep_api_url, api_key, setup_alerts
                )

        except Exception:
            self.logger.warning(
                "Failed to check or setup legacy alerting", exc_info=True
            )

        self.logger.info("Webhook successfuly setup")

    def _get_all_alerts(self, alerts_api: str, headers: dict) -> list:
        """Helper function to get all alerts with proper pagination"""
        all_alerts = []
        page = 0
        page_size = 1000  # Grafana's recommended limit

        try:
            while True:
                params = {
                    "dashboardId": None,
                    "panelId": None,
                    "limit": page_size,
                    "startAt": page * page_size,
                }

                self.logger.debug(
                    f"Fetching alerts page {page + 1}", extra={"params": params}
                )

                response = requests.get(
                    alerts_api, params=params, verify=False, headers=headers, timeout=30
                )
                response.raise_for_status()

                page_alerts = response.json()
                if not page_alerts:  # No more alerts to fetch
                    break

                all_alerts.extend(page_alerts)

                # If we got fewer alerts than the page size, we've reached the end
                if len(page_alerts) < page_size:
                    break

                page += 1
                time.sleep(0.2)  # Add delay to avoid rate limiting

            self.logger.info(f"Successfully fetched {len(all_alerts)} alerts")
            return all_alerts

        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to fetch alerts", extra={"error": str(e)})
            raise

    def _is_legacy_alerting_enabled(self) -> bool:
        """Check if legacy alerting is enabled by trying to access legacy endpoints"""
        try:
            headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
            notification_api = (
                f"{self.authentication_config.host}/api/alert-notifications"
            )
            response = requests.get(notification_api, verify=False, headers=headers)
            # If we get a 404, legacy alerting is disabled
            # If we get a 200, legacy alerting is enabled
            # If we get a 401/403, we don't have permissions
            return response.status_code == 200
        except Exception:
            self.logger.warning("Failed to check legacy alerting status", exc_info=True)
            return False

    def _update_dashboard_alert(
        self, dashboard_uid: str, panel_id: int, notification_uid: str, headers: dict
    ) -> bool:
        """Helper function to update a single dashboard alert"""
        try:
            # Get the dashboard
            dashboard_api = (
                f"{self.authentication_config.host}/api/dashboards/uid/{dashboard_uid}"
            )
            dashboard_response = requests.get(
                dashboard_api, verify=False, headers=headers, timeout=30
            )
            dashboard_response.raise_for_status()

            dashboard = dashboard_response.json()["dashboard"]
            updated = False

            # Find the panel and update its alert
            for panel in dashboard.get("panels", []):
                if panel.get("id") == panel_id and "alert" in panel:
                    if "notifications" not in panel["alert"]:
                        panel["alert"]["notifications"] = []
                    # Check if notification already exists
                    if not any(
                        notif.get("uid") == notification_uid
                        for notif in panel["alert"]["notifications"]
                    ):
                        panel["alert"]["notifications"].append(
                            {"uid": notification_uid}
                        )
                        updated = True

            if updated:
                # Update the dashboard
                update_dashboard_api = (
                    f"{self.authentication_config.host}/api/dashboards/db"
                )
                update_response = requests.post(
                    update_dashboard_api,
                    verify=False,
                    json={"dashboard": dashboard, "overwrite": True},
                    headers=headers,
                    timeout=30,
                )
                update_response.raise_for_status()
                return True

            return False

        except requests.exceptions.RequestException as e:
            self.logger.warning(
                f"Failed to update dashboard {dashboard_uid}", extra={"error": str(e)}
            )
            return False

    def _setup_legacy_alerting_webhook(
        self,
        webhook_name: str,
        keep_api_url: str,
        api_key: str,
        setup_alerts: bool = True,
    ):
        """Setup webhook for legacy alerting"""
        self.logger.info("Setting up legacy alerting notification channel")
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}

        try:
            # Create legacy notification channel
            notification_api = (
                f"{self.authentication_config.host}/api/alert-notifications"
            )
            notification = {
                "name": webhook_name,
                "type": "webhook",
                "isDefault": False,
                "sendReminder": False,
                "settings": {
                    "url": keep_api_url,
                    "httpMethod": "POST",
                    "username": "keep",
                    "password": api_key,
                },
            }

            # Check if notification channel exists
            existing_channels = requests.get(
                notification_api, verify=False, headers=headers
            ).json()
            channel_exists = any(
                channel
                for channel in existing_channels
                if channel.get("name") == webhook_name
            )

            if not channel_exists:
                response = requests.post(
                    notification_api, verify=False, json=notification, headers=headers
                )
                if not response.ok:
                    raise Exception(response.json())

                notification_uid = response.json().get("uid")
                self.logger.info("Created legacy notification channel")
            else:
                self.logger.info("Legacy notification channel already exists")
                notification_uid = next(
                    channel["uid"]
                    for channel in existing_channels
                    if channel.get("name") == webhook_name
                )

            if setup_alerts:
                alerts_api = f"{self.authentication_config.host}/api/alerts"

                # Get all alerts using the helper function
                all_alerts = self._get_all_alerts(alerts_api, headers)

                updated_count = 0
                for alert in all_alerts:
                    dashboard_uid = alert.get("dashboardUid")
                    panel_id = alert.get("panelId")

                    if dashboard_uid and panel_id:
                        if self._update_dashboard_alert(
                            dashboard_uid, panel_id, notification_uid, headers
                        ):
                            updated_count += 1
                        # Add delay to avoid rate limiting
                        time.sleep(0.1)

                self.logger.info(
                    f"Updated {updated_count} alerts with notification channel"
                )

        except Exception:
            self.logger.exception("Failed to setup legacy alerting")
            raise

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
        alert_renders = ALERTS[alert_type].get("renders", {})
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

        # Apply renders
        for param, choices in alert_renders.items():
            # replace annotations
            # HACK
            param_to_replace = "{{ " + param + " }}"
            alert_payload["annotations"]["summary"] = alert_payload["annotations"][
                "summary"
            ].replace(param_to_replace, random.choice(choices))

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
            "title": alert_type,
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
    alerts = provider.setup_webhook(
        "test", "http://localhost:3000/alerts/event/grafana", "some-api-key", True
    )
    print(alerts)
