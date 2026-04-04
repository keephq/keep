import dataclasses
import datetime
import json
import logging

import google.api_core
import google.api_core.exceptions
import google.oauth2.service_account
import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class VertexaiProviderAuthConfig:
    """Authentication configuration for the Vertex AI provider."""

    service_account_json: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "A service account JSON with Vertex AI and Cloud Monitoring access",
            "sensitive": True,
            "type": "file",
            "name": "service_account_json",
            "file_type": "application/json",
        }
    )
    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GCP Project ID where Vertex AI resources are deployed",
            "sensitive": False,
        }
    )
    location: str = dataclasses.field(
        default="us-central1",
        metadata={
            "required": False,
            "description": "GCP region for Vertex AI (e.g. us-central1, us-east1)",
            "sensitive": False,
        },
    )


class VertexaiProvider(BaseProvider, ProviderHealthMixin):
    """Get alerts from GCP Vertex AI into Keep via Cloud Monitoring."""

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send Vertex AI alerts from GCP Monitoring to Keep, follow these steps:

1. **Create a Notification Channel in GCP Monitoring:**
   - Go to GCP Monitoring → Notification Channels.
   - In the **Webhooks** section click **"ADD NEW"**.
   - Set:
     - **Endpoint URL**: `{keep_webhook_api_url}`
     - **Display Name**: `keep-vertexai-webhook`
   - Click **"Use HTTP Basic Auth"**:
     - **Auth Username**: `api_key`
     - **Auth Password**: `{api_key}`
   - Click **"Save"**.

2. **Create or Edit Alert Policies for Vertex AI:**
   - Go to GCP Monitoring → Alerting → Alert Policies.
   - Create policies targeting Vertex AI metrics such as:
     - `aiplatform.googleapis.com/prediction/online/error_count`
     - `aiplatform.googleapis.com/prediction/online/latencies`
     - `aiplatform.googleapis.com/prediction/online/prediction_count`
   - Under **"Notifications and name"**, select the `keep-vertexai-webhook` channel.
   - Click **"SAVE POLICY"**.

3. **Verify:**
   - Trigger a test notification or wait for an actual alert.
   - Verify the alert appears in Keep under the Vertex AI provider.

> **Note:** Vertex AI alerts are delivered through GCP Cloud Monitoring. The webhook payload format is identical to standard GCP Monitoring alerts with resource type `aiplatform.googleapis.com/Endpoint`.
"""

    # Severity mapping from GCP Monitoring severity labels
    SEVERITIES_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "ERROR": AlertSeverity.HIGH,
        "WARNING": AlertSeverity.WARNING,
        "INFO": AlertSeverity.INFO,
    }

    # Status mapping from GCP Monitoring incident state
    STATUS_MAP = {
        "CLOSED": AlertStatus.RESOLVED,
        "OPEN": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Vertex AI"
    PROVIDER_CATEGORY = ["AI", "Cloud Infrastructure"]
    FINGERPRINT_FIELDS = ["incident_id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="roles/aiplatform.user",
            description="Read access to Vertex AI resources (endpoints, models, deployments)",
            mandatory=True,
            alias="Vertex AI User",
        ),
        ProviderScope(
            name="roles/monitoring.viewer",
            description="Read access to GCP Cloud Monitoring alerts and metrics for Vertex AI",
            mandatory=True,
            alias="Monitoring Viewer",
        ),
    ]

    # Vertex AI metric types we specifically care about
    VERTEX_AI_METRIC_PREFIXES = [
        "aiplatform.googleapis.com/",
    ]

    # GCP Monitoring filter for Vertex AI alert policies
    VERTEX_AI_RESOURCE_FILTER = 'resource.type = "aiplatform.googleapis.com/Endpoint"'

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._service_account_data = json.loads(
            self.authentication_config.service_account_json
        )
        self._credentials = None
        self._monitoring_client = None

    def validate_config(self):
        self.authentication_config = VertexaiProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    @property
    def credentials(self):
        """Lazily build and return GCP credentials from service account JSON."""
        if self._credentials is None:
            self._credentials = (
                google.oauth2.service_account.Credentials.from_service_account_info(
                    self._service_account_data,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
            )
        return self._credentials

    @property
    def monitoring_client(self):
        """Lazily build and return the Cloud Monitoring AlertPolicy client."""
        if self._monitoring_client is None:
            try:
                from google.cloud import monitoring_v3

                self._monitoring_client = monitoring_v3.AlertPolicyServiceClient(
                    credentials=self.credentials
                )
            except ImportError:
                raise ImportError(
                    "google-cloud-monitoring is required. "
                    "Install it with: pip install google-cloud-monitoring"
                )
        return self._monitoring_client

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that the service account has the required GCP IAM scopes."""
        scopes = {}

        # Validate Vertex AI access via REST API
        try:
            project_id = self.authentication_config.project_id
            location = self.authentication_config.location

            # Refresh credentials
            import google.auth.transport.requests

            request = google.auth.transport.requests.Request()
            self.credentials.refresh(request)
            token = self.credentials.token

            # Call Vertex AI endpoints list to verify aiplatform.user role
            url = (
                f"https://{location}-aiplatform.googleapis.com/v1"
                f"/projects/{project_id}/locations/{location}/endpoints"
            )
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"pageSize": 1},
                timeout=10,
            )
            if resp.status_code == 403:
                scopes["roles/aiplatform.user"] = (
                    "Permission denied — ensure the service account has roles/aiplatform.user"
                )
            elif resp.status_code in (200, 204):
                scopes["roles/aiplatform.user"] = True
            else:
                scopes["roles/aiplatform.user"] = (
                    f"Unexpected status {resp.status_code}: {resp.text[:200]}"
                )
        except Exception as e:
            scopes["roles/aiplatform.user"] = str(e)

        # Validate Cloud Monitoring access
        try:
            project_name = f"projects/{self.authentication_config.project_id}"
            # Just list 1 alert policy to check access
            policies = list(
                self.monitoring_client.list_alert_policies(
                    request={"name": project_name, "page_size": 1}
                )
            )
            scopes["roles/monitoring.viewer"] = True
        except google.api_core.exceptions.PermissionDenied:
            scopes["roles/monitoring.viewer"] = (
                "Permission denied — ensure the service account has roles/monitoring.viewer"
            )
        except Exception as e:
            scopes["roles/monitoring.viewer"] = str(e)

        return scopes

    def setup_webhook(
        self,
        tenant_id: str,
        keep_api_url: str,
        api_key: str,
        setup_alerts: bool = True,
    ):
        """
        Webhook setup for Vertex AI alerts via GCP Cloud Monitoring.

        Vertex AI does not expose native webhooks. Instead, alerts are delivered
        through GCP Cloud Monitoring notification channels. This method creates
        a webhook notification channel in Cloud Monitoring pointing to Keep.

        Args:
            tenant_id: Keep tenant ID.
            keep_api_url: The Keep webhook ingest URL.
            api_key: Keep API key for webhook auth.
            setup_alerts: Whether to also create default Vertex AI alert policies.
        """
        self.logger.info("Setting up GCP Monitoring webhook for Vertex AI alerts")

        try:
            from google.cloud import monitoring_v3
        except ImportError:
            raise ImportError(
                "google-cloud-monitoring is required. "
                "Install it with: pip install google-cloud-monitoring"
            )

        project_name = f"projects/{self.authentication_config.project_id}"

        # Create notification channel (webhook)
        channel_client = monitoring_v3.NotificationChannelServiceClient(
            credentials=self.credentials
        )

        channel = monitoring_v3.NotificationChannel(
            type_="webhook_basicauth",
            display_name="keep-vertexai-webhook",
            description="Keep integration for Vertex AI alerts via GCP Monitoring",
            labels={
                "url": keep_api_url,
                "username": "api_key",
            },
            sensitive_labels=monitoring_v3.NotificationChannel.SensitiveLabels(
                password=api_key,
            ),
            enabled=True,
        )

        created_channel = channel_client.create_notification_channel(
            name=project_name,
            notification_channel=channel,
        )
        self.logger.info(
            f"Created notification channel: {created_channel.name}",
            extra={"channel_name": created_channel.name},
        )

        if setup_alerts:
            self._create_default_vertex_ai_alert_policies(
                project_name=project_name,
                notification_channel_name=created_channel.name,
            )

        return {
            "notification_channel_name": created_channel.name,
            "webhook_url": keep_api_url,
        }

    def _create_default_vertex_ai_alert_policies(
        self, project_name: str, notification_channel_name: str
    ):
        """Create default Vertex AI alert policies in GCP Monitoring."""
        try:
            from google.cloud import monitoring_v3
            from google.protobuf import duration_pb2
        except ImportError:
            self.logger.warning(
                "google-cloud-monitoring not available; skipping policy creation"
            )
            return

        alert_client = monitoring_v3.AlertPolicyServiceClient(
            credentials=self.credentials
        )

        default_policies = [
            {
                "display_name": "Vertex AI - High Prediction Error Rate",
                "condition_display_name": "Error Count > 10 per min",
                "filter": 'metric.type="aiplatform.googleapis.com/prediction/online/error_count" resource.type="aiplatform.googleapis.com/Endpoint"',
                "threshold_value": 10.0,
                "comparison": "COMPARISON_GT",
                "user_labels": {"keep": "true", "severity": "CRITICAL"},
            },
            {
                "display_name": "Vertex AI - High Prediction Latency",
                "condition_display_name": "P99 Latency > 10000ms",
                "filter": 'metric.type="aiplatform.googleapis.com/prediction/online/latencies" resource.type="aiplatform.googleapis.com/Endpoint"',
                "threshold_value": 10000.0,
                "comparison": "COMPARISON_GT",
                "user_labels": {"keep": "true", "severity": "WARNING"},
            },
            {
                "display_name": "Vertex AI - Endpoint Prediction Count Dropped",
                "condition_display_name": "Prediction Count = 0",
                "filter": 'metric.type="aiplatform.googleapis.com/prediction/online/prediction_count" resource.type="aiplatform.googleapis.com/Endpoint"',
                "threshold_value": 1.0,
                "comparison": "COMPARISON_LT",
                "user_labels": {"keep": "true", "severity": "CRITICAL"},
            },
        ]

        for policy_def in default_policies:
            try:
                condition = monitoring_v3.AlertPolicy.Condition(
                    display_name=policy_def["condition_display_name"],
                    condition_threshold=monitoring_v3.AlertPolicy.Condition.MetricThreshold(
                        filter=policy_def["filter"],
                        comparison=monitoring_v3.ComparisonType[
                            policy_def["comparison"]
                        ],
                        threshold_value=policy_def["threshold_value"],
                        duration=duration_pb2.Duration(seconds=300),
                    ),
                )
                policy = monitoring_v3.AlertPolicy(
                    display_name=policy_def["display_name"],
                    conditions=[condition],
                    notification_channels=[notification_channel_name],
                    user_labels=policy_def["user_labels"],
                    alert_strategy=monitoring_v3.AlertPolicy.AlertStrategy(
                        auto_close=duration_pb2.Duration(seconds=1800),
                    ),
                )
                created = alert_client.create_alert_policy(
                    name=project_name,
                    alert_policy=policy,
                )
                self.logger.info(
                    f"Created Vertex AI alert policy: {created.name}",
                    extra={"policy_name": created.name},
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to create alert policy '{policy_def['display_name']}': {e}"
                )

    def teardown_webhook(
        self,
        tenant_id: str,
        keep_api_url: str,
        api_key: str,
    ):
        """Remove the Keep webhook notification channel from GCP Monitoring."""
        self.logger.info("Tearing down GCP Monitoring webhook for Vertex AI alerts")
        try:
            from google.cloud import monitoring_v3
        except ImportError:
            raise ImportError(
                "google-cloud-monitoring is required. "
                "Install it with: pip install google-cloud-monitoring"
            )

        project_name = f"projects/{self.authentication_config.project_id}"
        channel_client = monitoring_v3.NotificationChannelServiceClient(
            credentials=self.credentials
        )

        # Find and delete channels matching our display name
        channels = channel_client.list_notification_channels(name=project_name)
        deleted = 0
        for channel in channels:
            if (
                channel.display_name == "keep-vertexai-webhook"
                and channel.labels.get("url") == keep_api_url
            ):
                try:
                    channel_client.delete_notification_channel(
                        name=channel.name, force=True
                    )
                    self.logger.info(
                        f"Deleted notification channel: {channel.name}",
                        extra={"channel_name": channel.name},
                    )
                    deleted += 1
                except Exception as e:
                    self.logger.error(
                        f"Failed to delete notification channel {channel.name}: {e}"
                    )

        self.logger.info(
            f"Teardown complete. Deleted {deleted} notification channel(s)."
        )

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull Vertex AI alert incidents from GCP Cloud Monitoring.

        Queries all alert policies whose conditions target Vertex AI (aiplatform)
        metrics and returns their active incidents as AlertDto objects.
        """
        try:
            from google.cloud import monitoring_v3
        except ImportError:
            self.logger.error(
                "google-cloud-monitoring not installed. Cannot pull Vertex AI alerts."
            )
            return []

        project_name = f"projects/{self.authentication_config.project_id}"
        alerts: list[AlertDto] = []

        try:
            # List all alert policies and filter to Vertex AI ones
            policies = self.monitoring_client.list_alert_policies(
                request={"name": project_name}
            )

            for policy in policies:
                if not self._is_vertexai_policy(policy):
                    continue

                # Fetch active incidents for this policy via the Cloud Monitoring REST API
                incidents = self._fetch_incidents_for_policy(policy)
                for incident in incidents:
                    try:
                        alert = self._incident_to_alert_dto(incident)
                        alerts.append(alert)
                    except Exception as e:
                        self.logger.error(
                            f"Failed to parse Vertex AI incident: {e}",
                            extra={"incident": incident},
                        )

        except google.api_core.exceptions.PermissionDenied as e:
            self.logger.error(
                f"Permission denied when listing Vertex AI alert policies: {e}"
            )
        except Exception as e:
            self.logger.error(f"Error pulling Vertex AI alerts: {e}")

        return alerts

    def _is_vertexai_policy(self, policy) -> bool:
        """Return True if an alert policy targets Vertex AI metrics."""
        for condition in policy.conditions:
            threshold = getattr(condition, "condition_threshold", None)
            if threshold and any(
                prefix in (threshold.filter or "")
                for prefix in self.VERTEX_AI_METRIC_PREFIXES
            ):
                return True
            # Also check by resource type
            if "aiplatform.googleapis.com" in (
                getattr(threshold, "filter", "") or ""
            ):
                return True
        return False

    def _fetch_incidents_for_policy(self, policy) -> list[dict]:
        """
        Fetch active incidents for a given alert policy via REST API.

        Falls back gracefully if the REST call fails.
        """
        try:
            import google.auth.transport.requests

            request = google.auth.transport.requests.Request()
            self.credentials.refresh(request)
            token = self.credentials.token

            project_id = self.authentication_config.project_id
            policy_id = policy.name.split("/")[-1]

            url = (
                f"https://monitoring.googleapis.com/v3"
                f"/projects/{project_id}/alertPolicies/{policy_id}/incidents"
            )
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"filter": "state=OPEN"},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("incidents", [])
            elif resp.status_code == 404:
                # No incidents endpoint — policy may not have any active incidents
                return []
            else:
                self.logger.warning(
                    f"Unexpected response fetching incidents for policy {policy.name}: "
                    f"{resp.status_code} {resp.text[:200]}"
                )
                return []
        except Exception as e:
            self.logger.warning(
                f"Could not fetch incidents for policy {policy.name}: {e}"
            )
            return []

    def _incident_to_alert_dto(self, incident: dict) -> AlertDto:
        """Convert a raw GCP Monitoring incident dict into an AlertDto."""
        incident_id = incident.get("incidentId", incident.get("incident_id", ""))
        state = incident.get("state", "OPEN").upper()
        status = self.STATUS_MAP.get(state, AlertStatus.FIRING)

        summary = incident.get("summary", "Vertex AI alert")
        url = incident.get("url", "")

        documentation = incident.get("documentation", {})
        if isinstance(documentation, dict):
            name = documentation.get("subject", summary) or "Vertex AI Alert"
            content = documentation.get("content", "")
        else:
            name = summary
            content = str(documentation)

        # Severity: check policy_user_labels first, then metadata
        policy_user_labels = incident.get("policyUserLabels", incident.get("policy_user_labels", {}))
        metadata = incident.get("metadata", {})
        system_labels = metadata.get("systemLabels", metadata.get("system_labels", {}))

        raw_severity = (
            policy_user_labels.get("severity")
            or system_labels.get("severity")
            or "WARNING"
        ).upper()
        severity = self.SEVERITIES_MAP.get(raw_severity, AlertSeverity.WARNING)

        # Timestamp
        started_at = incident.get("startedAt", incident.get("started_at"))
        if started_at:
            try:
                event_time = datetime.datetime.fromtimestamp(
                    int(started_at), tz=datetime.timezone.utc
                )
            except (ValueError, TypeError):
                event_time = datetime.datetime.now(tz=datetime.timezone.utc)
        else:
            event_time = datetime.datetime.now(tz=datetime.timezone.utc)

        event_time_str = event_time.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )

        # Extract resource details
        resource = incident.get("resource", {})
        resource_labels = resource.get("labels", {})
        endpoint_id = resource_labels.get("endpoint_id", "")
        location = resource_labels.get("location", self.authentication_config.location)

        # Build alert
        alert = AlertDto(
            id=incident_id,
            name=name,
            status=status,
            lastReceived=event_time_str,
            source=["vertexai"],
            description=summary,
            severity=severity,
            url=url,
            incident_id=incident_id,
            endpoint_id=endpoint_id,
            location=location,
            project_id=self.authentication_config.project_id,
            content=content,
            vertexai=incident,  # raw incident data
        )
        alert.fingerprint = BaseProvider.get_alert_fingerprint(
            alert, VertexaiProvider.FINGERPRINT_FIELDS
        )
        return alert

    def pull_alerts(self) -> list[AlertDto]:
        return self._get_alerts()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a webhook alert payload (GCP Monitoring incident format) into an AlertDto.

        This is called when Vertex AI alerts are received via the GCP Monitoring
        webhook notification channel configured to point at Keep.
        """
        incident = event.get("incident", {})
        description = incident.pop("summary", "")
        state = incident.pop("state", "OPEN").upper()
        status = VertexaiProvider.STATUS_MAP.get(state, AlertStatus.FIRING)
        url = incident.pop("url", "")

        documentation = incident.pop("documentation", {})
        if isinstance(documentation, dict):
            name = (
                documentation.get("subject", description)
                or "Vertex AI Alert (No subject)"
            )
            content = documentation.get("content", "")
        else:
            name = "Vertex AI Test Notification"
            content = str(documentation)

        incident_id = incident.get("incident_id", incident.get("incidentId", ""))

        # Severity
        policy_user_labels = incident.get("policy_user_labels", {})
        if "severity" in incident:
            raw_severity = incident.pop("severity", "WARNING").upper()
        else:
            raw_severity = policy_user_labels.get("severity", "WARNING").upper()
        severity = VertexaiProvider.SEVERITIES_MAP.get(raw_severity, AlertSeverity.WARNING)

        # Timestamp
        event_time = incident.get("started_at")
        if event_time:
            event_time = datetime.datetime.fromtimestamp(
                int(event_time), tz=datetime.timezone.utc
            )
        else:
            event_time = datetime.datetime.now(tz=datetime.timezone.utc)
        event_time_str = event_time.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )

        # Resource
        resource = incident.get("resource", {})
        resource_labels = resource.get("labels", {})
        endpoint_id = resource_labels.get("endpoint_id", "")
        location = resource_labels.get("location", "")
        project_id = resource_labels.get("project_id", "")

        extra = {}
        if "service" in policy_user_labels:
            extra["service"] = policy_user_labels["service"]
        if "application" in policy_user_labels:
            extra["application"] = policy_user_labels["application"]

        alert = AlertDto(
            id=incident_id,
            name=name,
            status=status,
            lastReceived=event_time_str,
            source=["vertexai"],
            description=description,
            severity=severity,
            url=url,
            incident_id=incident_id,
            endpoint_id=endpoint_id,
            location=location,
            project_id=project_id,
            content=content,
            vertexai=incident,
            **extra,
        )
        alert.fingerprint = BaseProvider.get_alert_fingerprint(
            alert, VertexaiProvider.FINGERPRINT_FIELDS
        )
        return alert


if __name__ == "__main__":
    from keep.providers.providers_factory import ProvidersFactory

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    with open("sa.json") as f:
        service_account_data = f.read()

    config = {
        "authentication": {
            "service_account_json": service_account_data,
            "project_id": "my-gcp-project",
            "location": "us-central1",
        }
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="vertexai-demo",
        provider_type="vertexai",
        provider_config=config,
    )
    scopes = provider.validate_scopes()
    print("Scopes:", scopes)

    alerts = provider.pull_alerts()
    print(f"Found {len(alerts)} Vertex AI alerts")
    for alert in alerts:
        print(f"  [{alert.severity}] {alert.name}: {alert.description}")
