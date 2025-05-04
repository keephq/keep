"""
Grafana Provider is a class that allows to ingest/digest data from Grafana.
"""

import dataclasses
import datetime
import hashlib
import json
import logging
import time

import pydantic
import requests
from packaging.version import Version

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import (
    BaseProvider,
    BaseTopologyProvider,
    ProviderHealthMixin,
)
from keep.providers.base.provider_exceptions import GetAlertException
from keep.providers.grafana_provider.grafana_alert_format_description import (
    GrafanaAlertFormatDescription,
)
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


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
    datasource_uid: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Datasource UID",
            "hint": "Provide if you want to pull topology data",
        },
        default="",
    )


class GrafanaProvider(BaseTopologyProvider, ProviderHealthMixin):
    PROVIDER_DISPLAY_NAME = "Grafana"
    """Pull/Push alerts & Topology map from Grafana."""

    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    KEEP_GRAFANA_WEBHOOK_INTEGRATION_NAME = "keep-grafana-webhook-integration"
    FINGERPRINT_FIELDS = ["fingerprint"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """If your Grafana is unreachable from Keep, you can use the following webhook url to configure Grafana to send alerts to Keep:

    1. In Grafana, go to the Alerting tab in the Grafana dashboard.
    2. Click on Contact points in the left sidebar and create a new one.
    3. Give it a name and select Webhook as kind of contact point with webhook url as {keep_webhook_api_url}.
    4. Add 'X-API-KEY' as the request header {api_key}.
    5. Save the webhook.
    6. Click on Notification policies in the left sidebar
    7. Click on "New child policy" under the "Default policy"
    8. Remove all matchers until you see the following: "If no matchers are specified, this notification policy will handle all alert instances."
    9. Chose the webhook contact point you have just created under Contact point and click "Save Policy"
    """

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
    def get_service(alert: dict) -> str:
        """
        Get service from alert.
        """
        labels = alert.get("labels", {})
        return alert.get("service", labels.get("service", "unknown"))

    @staticmethod
    def calculate_fingerprint(alert: dict) -> str:
        """
        Calculate fingerprint for alert.
        """
        labels = alert.get("labels", {})
        fingerprint = labels.get("fingerprint", "")
        if fingerprint:
            logger.debug("Fingerprint provided in alert")
            return fingerprint

        fingerprint_string = None
        if not labels:
            logger.warning(
                "No labels found in alert will use old behaviour",
                extra={
                    "labels": labels,
                },
            )
        else:
            try:
                logger.info(
                    "No fingerprint in alert, calculating fingerprint by labels"
                )
                fingerprint_string = json.dumps(labels)
            except Exception:
                logger.exception(
                    "Failed to calculate fingerprint",
                    extra={
                        "labels": labels,
                    },
                )

        # from some reason, the fingerprint is not provided in the alert + no labels or failed to calculate
        if not fingerprint_string:
            # old behavior
            service = GrafanaProvider.get_service(alert)
            fingerprint_string = alert.get(
                "fingerprint", alert.get("alertname", "") + service
            )

        fingerprint = hashlib.sha256(fingerprint_string.encode()).hexdigest()
        return fingerprint

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # Check if this is a legacy alert based on structure
        if "evalMatches" in event:
            return GrafanaProvider._format_legacy_alert(event)

        alerts = event.get("alerts", [])

        logger.info("Formatting Grafana alerts", extra={"num_of_alerts": len(alerts)})

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
            fingerprint = GrafanaProvider.calculate_fingerprint(alert)
            environment = labels.get(
                "deployment_environment", labels.get("environment", "unknown")
            )

            extra = {}

            annotations = alert.get("annotations", {})
            if annotations:
                extra["annotations"] = annotations
            values = alert.get("values", {})
            if values:
                extra["values"] = values

            url = alert.get("generatorURL", None)
            image_url = alert.get("imageURL", None)
            dashboard_url = alert.get("dashboardURL", None)
            panel_url = alert.get("panelURL", None)

            # backward compatibility
            description = alert.get("annotations", {}).get("summary", "")
            if not description:
                description = alert.get("annotations", {}).get("description")

            valueString = alert.get("valueString")

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
                description=description,
                source=["grafana"],
                labels=labels,
                url=url or None,
                imageUrl=image_url or None,
                dashboardUrl=dashboard_url or None,
                panelUrl=panel_url or None,
                valueString=valueString,
                **extra,  # add annotations and values
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

    def _get_grafana_version(self) -> str:
        """Get the Grafana version."""
        try:
            headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
            health_url = f"{self.authentication_config.host}/api/health"

            resp = requests.get(health_url, verify=False, headers=headers, timeout=5)

            if resp.ok:
                health_data = resp.json()
                return health_data.get("version", "unknown")
            else:
                self.logger.warning(
                    f"Failed to get Grafana version: {resp.status_code}"
                )
                return "unknown"
        except Exception as e:
            self.logger.error(f"Error getting Grafana version: {str(e)}")
            return "unknown"

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
            grafana_version = self._get_grafana_version()
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
            self.logger.info("Checking legacy alerting")
            if self._is_legacy_alerting_enabled():
                self.logger.info("Legacy alerting is enabled")
                self._setup_legacy_alerting_webhook(
                    webhook_name, keep_api_url, api_key, setup_alerts
                )
                self.logger.info("Legacy alerting setup successful")

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
            self.logger.debug(f"Using notification API endpoint: {notification_api}")

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
            self.logger.debug(f"Prepared notification config: {notification}")

            # Check if notification channel exists
            self.logger.info("Checking for existing notification channels")
            existing_channels = requests.get(
                notification_api, verify=False, headers=headers
            ).json()
            self.logger.debug(f"Found {len(existing_channels)} existing channels")

            channel_exists = any(
                channel
                for channel in existing_channels
                if channel.get("name") == webhook_name
            )

            if not channel_exists:
                self.logger.info(f"Creating new notification channel '{webhook_name}'")
                response = requests.post(
                    notification_api, verify=False, json=notification, headers=headers
                )
                if not response.ok:
                    error_msg = response.json()
                    self.logger.error(
                        f"Failed to create notification channel: {error_msg}"
                    )
                    raise Exception(error_msg)

                notification_uid = response.json().get("uid")
                self.logger.info(
                    f"Created legacy notification channel with UID: {notification_uid}"
                )
            else:
                self.logger.info(
                    f"Legacy notification channel '{webhook_name}' already exists"
                )
                notification_uid = next(
                    channel["uid"]
                    for channel in existing_channels
                    if channel.get("name") == webhook_name
                )
                self.logger.debug(
                    f"Using existing notification channel UID: {notification_uid}"
                )

            if setup_alerts:
                alerts_api = f"{self.authentication_config.host}/api/alerts"
                self.logger.info("Starting alert setup process")

                # Get all alerts using the helper function
                self.logger.info("Fetching all alerts")
                all_alerts = self._get_all_alerts(alerts_api, headers)
                self.logger.info(f"Found {len(all_alerts)} alerts to process")

                updated_count = 0
                for alert in all_alerts:
                    dashboard_uid = alert.get("dashboardUid")
                    panel_id = alert.get("panelId")

                    if dashboard_uid and panel_id:
                        self.logger.debug(
                            f"Processing alert - Dashboard: {dashboard_uid}, Panel: {panel_id}"
                        )
                        if self._update_dashboard_alert(
                            dashboard_uid, panel_id, notification_uid, headers
                        ):
                            updated_count += 1
                            self.logger.debug(
                                f"Successfully updated alert {updated_count}"
                            )
                        # Add delay to avoid rate limiting
                        time.sleep(0.1)

                self.logger.info(
                    f"Completed alert updates - Updated {updated_count} alerts with notification channel"
                )

        except Exception as e:
            self.logger.exception(f"Failed to setup legacy alerting: {str(e)}")
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

    def _get_alerts_datasource(self) -> list:
        """
        Get raw alerts from all available datasources (Prometheus, Loki, Grafana, Alertmanager).
        Returns a list of raw alert dictionaries, or an empty list if there are errors.
        """
        self.logger.info("Starting to fetch alerts from Grafana datasources")

        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        all_alerts = []

        # Step 1: Get all datasources
        try:
            self.logger.info("Fetching list of datasources")
            datasources_url = f"{self.authentication_config.host}/api/datasources"
            datasources_resp = requests.get(
                datasources_url, headers=headers, timeout=5, verify=False
            )

            if datasources_resp.status_code != 200:
                self.logger.error(
                    f"Failed to get datasources: {datasources_resp.status_code}",
                    extra={"response_text": datasources_resp.text[:500]},
                )
                return []

            self.logger.info(
                f"Successfully fetched datasources, got {len(datasources_resp.json())} datasources"
            )
        except Exception as e:
            self.logger.error(f"Error fetching datasources list: {str(e)}")
            return []

        # Step 2: Extract relevant datasources (Prometheus, Loki, Mimir)
        alert_datasources = []
        try:
            for ds in datasources_resp.json():
                if (
                    ds.get("type") in ["prometheus", "loki"]
                    or "mimir" in ds.get("name", "").lower()
                ):
                    alert_datasources.append(
                        {
                            "uid": ds.get("uid"),
                            "name": ds.get("name"),
                            "type": ds.get("type"),
                        }
                    )

            self.logger.info(
                f"Found {len(alert_datasources)} alert-capable datasources"
            )
        except Exception as e:
            self.logger.error(f"Error parsing datasources: {str(e)}")
            return []

        # Step 3: Query alerts from each datasource
        for ds in alert_datasources:
            try:
                # Log the datasource we're about to query
                self.logger.info(
                    f"Querying alerts for datasource: {ds.get('name')}",
                    extra={"datasource": ds},
                )

                # Different endpoint based on datasource type
                if ds.get("type") == "loki":
                    # For Loki, use the Prometheus-compatible alerts endpoint
                    alert_url = f"{self.authentication_config.host}/api/datasources/proxy/uid/{ds.get('uid')}/prometheus/api/v1/alerts"
                else:
                    # For Prometheus/Mimir, use the standard alerts endpoint
                    alert_url = f"{self.authentication_config.host}/api/datasources/proxy/uid/{ds.get('uid')}/api/v1/alerts"

                # Query the alerts endpoint
                self.logger.info(f"Querying {ds.get('name')} alerts at: {alert_url}")
                resp = requests.get(alert_url, headers=headers, timeout=8, verify=False)

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "success" and "alerts" in data.get(
                        "data", {}
                    ):
                        ds_alerts = data["data"]["alerts"]

                        if ds_alerts:  # Only process non-empty alert lists
                            self.logger.info(
                                f"Found {len(ds_alerts)} alerts in {ds.get('name')}"
                            )

                            for alert in ds_alerts:
                                # Tag with source name and type
                                alert["datasource"] = ds.get("name")
                                alert["datasource_type"] = ds.get("type")

                            all_alerts.extend(ds_alerts)
                        else:
                            self.logger.info(f"No alerts found for {ds.get('name')}")
                    else:
                        self.logger.info(
                            f"No alerts data found in response from {ds.get('name')}",
                            extra={
                                "status": data.get("status"),
                                "has_data": "data" in data,
                                "has_alerts": "data" in data
                                and "alerts" in data.get("data", {}),
                            },
                        )
                else:
                    self.logger.warning(
                        f"Failed to get alerts for {ds.get('name')}: {resp.status_code}",
                        extra={"response": resp.text[:500]},  # Limit response log size
                    )
            except Exception as e:
                self.logger.error(
                    f"Error querying alerts for {ds.get('name')}: {str(e)}",
                    exc_info=True,
                )
                # Continue to the next datasource
                continue

        # Step 4: Process and format the alerts
        formatted_alerts = []
        for alert in all_alerts:
            try:
                # Format the alert using the existing method
                alertname = alert.get(
                    "name",
                    alert.get("alertname", alert.get("labels", {}).get("alertname")),
                )
                if not alertname:
                    logger.warning(
                        "Alert name not found, using default",
                        extra={
                            "alert": alert,
                        },
                    )
                    alertname = "Grafana Alert [Unknown]"
                severity = alert.get(
                    "severity", alert.get("labels", {}).get("severity")
                )
                if not severity:
                    logger.warning(
                        "Alert severity not found, using default",
                        extra={
                            "alert": alert,
                        },
                    )
                    severity = "info"
                severity = GrafanaProvider.SEVERITIES_MAP.get(
                    severity, AlertSeverity.INFO
                )

                status = alert.get("state")
                if not status:
                    logger.warning(
                        "Alert status not found, using default",
                        extra={
                            "alert": alert,
                        },
                    )
                    status = "firing"
                status = GrafanaProvider.STATUS_MAP.get(status, AlertStatus.FIRING)

                labels = alert.get("labels", {})
                # pop severity from labels to avoid duplication
                labels.pop("severity", None)
                annotations = alert.get("annotations", {})

                description = annotations.get("description", annotations.get("summary"))
                try:
                    alert_dto = AlertDto(
                        name=alertname,
                        status=status,
                        severity=severity,
                        source=["grafana"],
                        labels=labels,
                        annotations=annotations,
                        datasource=alert.get("datasource"),
                        datasource_type=alert.get("datasource_type"),
                        value=alert.get("value"),
                    )
                    if description:
                        alert_dto.description = description
                    formatted_alerts.append(alert_dto)
                except Exception:
                    self.logger.exception(
                        "Failed to format datasoruce alert",
                        extra={
                            "alert": alert,
                        },
                    )
                    continue
            except Exception as e:
                self.logger.error(
                    f"Error formatting alert: {str(e)}", extra={"alert": alert}
                )

        self.logger.info(
            f"Total alerts found across all datasources: {len(formatted_alerts)}"
        )
        return formatted_alerts

    def _get_alerts(self) -> list[AlertDto]:
        self.logger.info("Starting to fetch alerts from Grafana")

        # First get alerts from datasources directly
        datasource_alerts = self._get_alerts_datasource()
        self.logger.info(f"Found {len(datasource_alerts)} alerts from datasources")

        # Get Grafana version to determine best approach for history API
        grafana_version = self._get_grafana_version()
        self.logger.info(f"Detected Grafana version: {grafana_version}")

        history_alerts = []

        # Calculate time range (7 days ago to now)
        week_ago = int(
            (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
        )
        now = int(datetime.datetime.now().timestamp())
        self.logger.info(
            f"Using time range for alerts: from={week_ago} to={now}",
            extra={"from_timestamp": week_ago, "to_timestamp": now},
        )

        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}

        # First try the general history API (works in older Grafana versions)
        try:
            api_endpoint = f"{self.authentication_config.host}/api/v1/rules/history?from={week_ago}&to={now}&limit=0"
            self.logger.info(f"Querying Grafana history API endpoint: {api_endpoint}")

            response = requests.get(
                api_endpoint, verify=False, headers=headers, timeout=5
            )
            self.logger.info(
                f"Received response from Grafana history API with status code: {response.status_code}"
            )

            if response.ok:
                # Process the response
                events_history = response.json()
                events_data = events_history.get("data", {})

                if events_data and "values" in events_data:
                    events_data_values = events_data.get("values")
                    if events_data_values and len(events_data_values) >= 2:
                        # If we have values, extract the events and timestamps
                        events = events_data_values[1]
                        events_time = events_data_values[0]

                        self.logger.info(f"Found {len(events)} events in history API")

                        for i in range(0, len(events)):
                            event = events[i]
                            try:
                                event_labels = event.get("labels", {})
                                alert_name = event_labels.get("alertname")
                                alert_status = event_labels.get(
                                    "alertstate", event.get("current")
                                )

                                # Map status to Keep format
                                alert_status = GrafanaProvider.STATUS_MAP.get(
                                    alert_status, AlertStatus.FIRING
                                )

                                # Extract other fields
                                alert_severity = event_labels.get("severity")
                                alert_severity = GrafanaProvider.SEVERITIES_MAP.get(
                                    alert_severity, AlertSeverity.INFO
                                )
                                environment = event_labels.get("environment", "unknown")
                                fingerprint = event_labels.get("fingerprint")
                                description = event.get("error", "")
                                rule_id = event.get("ruleUID")
                                condition = event.get("condition")

                                # Convert timestamp
                                timestamp = datetime.datetime.fromtimestamp(
                                    events_time[i] / 1000
                                ).isoformat()

                                # Create AlertDto
                                alert_dto = AlertDto(
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
                                history_alerts.append(alert_dto)
                            except Exception as e:
                                self.logger.error(
                                    f"Error processing event {i+1}",
                                    extra={"event": event, "error": str(e)},
                                )

                self.logger.info(
                    f"Successfully processed {len(history_alerts)} alerts from Grafana history API"
                )
            else:
                # If general API fails with 'ruleUID is required' error in newer Grafana versions
                if "ruleUID is required" in response.text:
                    self.logger.info(
                        "Grafana version requires ruleUID parameter, trying per-rule approach"
                    )

                    # Get all rules first
                    rules_endpoint = (
                        f"{self.authentication_config.host}/api/alerting/rules"
                    )
                    self.logger.info(f"Fetching alert rules from: {rules_endpoint}")

                    rules_response = requests.get(
                        rules_endpoint, verify=False, headers=headers, timeout=5
                    )

                    if rules_response.ok:
                        rules_data = rules_response.json()
                        rule_uids = []

                        # Extract all rule UIDs
                        for group in rules_data.get("data", {}).get("groups", []):
                            for rule in group.get("rules", []):
                                if "uid" in rule:
                                    rule_uids.append(rule["uid"])

                        self.logger.info(f"Found {len(rule_uids)} rule UIDs")

                        # For each rule UID, get its history
                        for rule_uid in rule_uids:
                            rule_history_url = f"{self.authentication_config.host}/api/v1/rules/history?from={week_ago}&to={now}&limit=100&ruleUID={rule_uid}"

                            try:
                                rule_resp = requests.get(
                                    rule_history_url,
                                    verify=False,
                                    headers=headers,
                                    timeout=5,
                                )

                                if rule_resp.ok:
                                    rule_history = rule_resp.json()
                                    rule_data = rule_history.get("data", {})

                                    if rule_data and "values" in rule_data:
                                        rule_values = rule_data.get("values")
                                        if rule_values and len(rule_values) >= 2:
                                            rule_events = rule_values[1]
                                            rule_times = rule_values[0]

                                            self.logger.info(
                                                f"Found {len(rule_events)} events for rule {rule_uid}"
                                            )

                                            for i in range(0, len(rule_events)):
                                                event = rule_events[i]
                                                try:
                                                    event_labels = event.get(
                                                        "labels", {}
                                                    )
                                                    alert_name = event_labels.get(
                                                        "alertname", f"Rule {rule_uid}"
                                                    )
                                                    alert_status = event_labels.get(
                                                        "alertstate",
                                                        event.get("current"),
                                                    )
                                                    alert_status = (
                                                        GrafanaProvider.STATUS_MAP.get(
                                                            alert_status,
                                                            AlertStatus.FIRING,
                                                        )
                                                    )
                                                    alert_severity = event_labels.get(
                                                        "severity"
                                                    )
                                                    alert_severity = GrafanaProvider.SEVERITIES_MAP.get(
                                                        alert_severity,
                                                        AlertSeverity.INFO,
                                                    )
                                                    environment = event_labels.get(
                                                        "environment", "unknown"
                                                    )
                                                    fingerprint = event_labels.get(
                                                        "fingerprint", rule_uid
                                                    )
                                                    description = event.get("error", "")
                                                    condition = event.get("condition")

                                                    # Convert timestamp
                                                    timestamp = (
                                                        datetime.datetime.fromtimestamp(
                                                            rule_times[i] / 1000
                                                        ).isoformat()
                                                    )

                                                    alert_dto = AlertDto(
                                                        id=f"{rule_uid}_{i}",
                                                        fingerprint=fingerprint,
                                                        name=alert_name,
                                                        status=alert_status,
                                                        severity=alert_severity,
                                                        environment=environment,
                                                        description=description,
                                                        lastReceived=timestamp,
                                                        rule_id=rule_uid,
                                                        condition=condition,
                                                        labels=event_labels,
                                                        source=["grafana"],
                                                    )
                                                    history_alerts.append(alert_dto)
                                                except Exception as e:
                                                    self.logger.error(
                                                        f"Error processing event for rule {rule_uid}",
                                                        extra={
                                                            "event": event,
                                                            "error": str(e),
                                                        },
                                                    )
                            except Exception as e:
                                self.logger.error(
                                    f"Error processing history for rule {rule_uid}",
                                    extra={"error": str(e)},
                                )
                    # if response is 404, it means the API is not available
                    elif rules_response.status_code == 404:
                        # if legacy alerting is not enabled, we can assume the API is not available
                        self.logger.error("Grafana history API not available")
                    else:
                        self.logger.error(
                            "Failed to get alerts from Grafana history API",
                            extra={
                                "status_code": response.status_code,
                                "response_text": response.text,
                                "api_endpoint": api_endpoint,
                            },
                        )
                    self.logger.info(
                        f"Processed {len(history_alerts)} alerts from per-rule history API"
                    )
                else:
                    self.logger.error(
                        "Failed to get alerts from Grafana history API",
                        extra={
                            "status_code": response.status_code,
                            "response_text": response.text,
                            "api_endpoint": api_endpoint,
                        },
                    )
        except Exception as e:
            self.logger.error(
                "Error querying Grafana history API", extra={"error": str(e)}
            )

        # Also try to get alerts from Alertmanager
        alertmanager_alerts = []
        try:
            alertmanager_url = f"{self.authentication_config.host}/api/alertmanager/grafana/api/v2/alerts"
            self.logger.info(f"Querying Alertmanager at: {alertmanager_url}")

            am_resp = requests.get(
                alertmanager_url, verify=False, headers=headers, timeout=5
            )

            if am_resp.ok:
                am_alerts_data = am_resp.json()

                if am_alerts_data:
                    self.logger.info(
                        f"Found {len(am_alerts_data)} alerts in Alertmanager"
                    )

                    for i, alert in enumerate(am_alerts_data):
                        try:
                            # Extract alert properties
                            labels = alert.get("labels", {})
                            annotations = alert.get("annotations", {})

                            # Extract alert name
                            alert_name = labels.get("alertname", f"Alert_{i}")

                            # Determine status
                            alert_status = AlertStatus.FIRING
                            if alert.get("status", {}).get("state") == "suppressed":
                                alert_status = AlertStatus.SUPPRESSED
                            elif (
                                alert.get("endsAt")
                                and alert.get("endsAt") != "0001-01-01T00:00:00Z"
                            ):
                                alert_status = AlertStatus.RESOLVED

                            # Extract severity
                            alert_severity = labels.get("severity", "info")
                            alert_severity = GrafanaProvider.SEVERITIES_MAP.get(
                                alert_severity, AlertSeverity.INFO
                            )

                            # Create AlertDto
                            alert_dto = AlertDto(
                                id=alert.get("fingerprint", str(i)),
                                fingerprint=alert.get("fingerprint"),
                                name=alert_name,
                                status=alert_status,
                                severity=alert_severity,
                                environment=labels.get("environment", "unknown"),
                                description=annotations.get(
                                    "description", annotations.get("summary", "")
                                ),
                                lastReceived=alert.get("startsAt"),
                                rule_id=labels.get("ruleId"),
                                condition="",
                                labels=labels,
                                source=["grafana"],
                            )
                            alertmanager_alerts.append(alert_dto)
                        except Exception as e:
                            self.logger.error(
                                f"Error processing Alertmanager alert {i}",
                                extra={"alert": alert, "error": str(e)},
                            )
            else:
                self.logger.warning(
                    f"Failed to get alerts from Alertmanager: {am_resp.status_code}"
                )
        except Exception as e:
            self.logger.error("Error querying Alertmanager", extra={"error": str(e)})

        # Combine all alert sources
        all_alerts = datasource_alerts + history_alerts + alertmanager_alerts
        self.logger.info(f"Total alerts found from all sources: {len(all_alerts)}")

        return all_alerts

    @classmethod
    def simulate_alert(cls, **kwargs) -> dict:
        import hashlib
        import json
        import random

        from keep.providers.grafana_provider.alerts_mock import ALERTS

        alert_type = kwargs.get("alert_type")
        if not alert_type:
            alert_type = random.choice(list(ALERTS.keys()))

        to_wrap_with_provider_type = kwargs.get("to_wrap_with_provider_type")

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

        final_payload = {
            "alerts": [alert_payload],
            "severity": alert_payload.get("labels", {}).get("severity"),
            "title": alert_type,
        }
        if to_wrap_with_provider_type:
            return {"keep_source_type": "grafana", "event": final_payload}
        return final_payload

    def query_datasource_for_topology(self):
        self.logger.info("Attempting to query datasource for topology data.")
        headers = {
            "Authorization": f"Bearer {self.authentication_config.token}",
            "Content-Type": "application/json",
        }
        json_data = {
            "queries": [
                {
                    "format": "table",
                    "refId": "traces_service_graph_request_total",
                    "expr": "sum by (client, server) (rate(traces_service_graph_request_total[3600s]))",
                    "instant": True,
                    "exemplar": False,
                    "requestId": "service_map_request",
                    "utcOffsetSec": 19800,
                    "interval": "",
                    "legendFormat": "",
                    "datasource": {
                        "uid": self.authentication_config.datasource_uid,
                    },
                    "datasourceId": 1,
                    "intervalMs": 5000,
                    "maxDataPoints": 954,
                },
                {
                    "format": "table",
                    "refId": "traces_service_graph_request_server_seconds_sum",
                    "expr": "sum by (client, server) (rate(traces_service_graph_request_server_seconds_sum[3600s]))",
                    "instant": True,
                    "exemplar": False,
                    "requestId": "service_map_request_avg",
                    "utcOffsetSec": 19800,
                    "interval": "",
                    "legendFormat": "",
                    "datasource": {
                        "uid": self.authentication_config.datasource_uid,
                    },
                    "datasourceId": 1,
                    "intervalMs": 5000,
                    "maxDataPoints": 954,
                },
            ],
            "to": "now",
        }
        try:
            response = requests.post(
                f"{self.authentication_config.host}/api/ds/query",
                verify=False,
                headers=headers,
                json=json_data,
                timeout=10,
            )
            if response.status_code != 200:
                raise Exception(response.text)
            return response.json()
        except Exception as e:
            self.logger.error(
                "Error while querying datasource for topology map",
                extra={"exception": str(e)},
            )

    @staticmethod
    def __extract_schema_value_pair(results, query: str):
        client_server_data = {}
        for frames in results.get(query, {}).get("frames", []):
            value_index = 0
            for fields in frames.get("schema", {}).get("fields", []):
                if (
                    "labels" in fields
                    and "client" in fields["labels"]
                    and "server" in fields["labels"]
                ):
                    client_server_data[
                        (fields["labels"]["client"], fields["labels"]["server"])
                    ] = float(frames["data"]["values"][value_index][0])
                    break
                value_index += 1
        return client_server_data

    def pull_topology(self):
        self.logger.info("Pulling Topology data from Grafana...")
        if not self.authentication_config.datasource_uid:
            self.logger.debug("No datasource uid found, skipping topology pull")
            return [], {}
        try:
            service_topology = {}
            results = self.query_datasource_for_topology().get("results", {})

            self.logger.info(
                "Scraping traces_service_graph_request_total data from the response"
            )
            requests_per_second_data = GrafanaProvider.__extract_schema_value_pair(
                results=results, query="traces_service_graph_request_total"
            )

            self.logger.info(
                "Scraping traces_service_graph_request_server_seconds_sum data from the response"
            )
            total_response_times_data = GrafanaProvider.__extract_schema_value_pair(
                results=results, query="traces_service_graph_request_server_seconds_sum"
            )

            self.logger.info("Building Topology map.")
            for client_server in requests_per_second_data:
                client, server = client_server
                requests_per_second = requests_per_second_data[client_server]
                total_response_time = total_response_times_data.get(client_server, None)

                if client not in service_topology:
                    service_topology[client] = TopologyServiceInDto(
                        source_provider_id=self.provider_id,
                        service=client,
                        display_name=client,
                    )
                if server not in service_topology:
                    service_topology[server] = TopologyServiceInDto(
                        source_provider_id=self.provider_id,
                        service=server,
                        display_name=server,
                    )

                service_topology[client].dependencies[server] = (
                    "unknown"
                    if total_response_time is None
                    else f"{round(requests_per_second, 2)}r/sec || {round((total_response_time / requests_per_second) * 1000, 2)}ms/r"
                )
            self.logger.info("Successfully pulled Topology data from Grafana...")
            return list(service_topology.values()), {}
        except Exception as e:
            self.logger.error(
                "Error while pulling topology data from Grafana",
                extra={"exception": str(e)},
            )
            raise e


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
    alerts = provider.get_alerts()
    alerts = provider.setup_webhook(
        "test", "http://localhost:3000/alerts/event/grafana", "some-api-key", True
    )
    print(alerts)
