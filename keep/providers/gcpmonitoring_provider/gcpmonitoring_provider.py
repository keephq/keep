import dataclasses
import datetime
import json
import logging

import google.api_core
import google.api_core.exceptions
import google.cloud.logging
import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod
from keep.providers.providers_factory import ProvidersFactory


class LogEntry(pydantic.BaseModel):
    timestamp: datetime.datetime
    severity: str
    payload: dict | None
    http_request: dict | None
    payload_exists: bool = False
    http_request_exists: bool = False

    @pydantic.validator("severity", pre=True)
    def validate_severity(cls, severity):
        if severity is None:
            return "INFO"
        return severity


@pydantic.dataclasses.dataclass
class GcpmonitoringProviderAuthConfig:
    service_account_json: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "A service account JSON with logging viewer role",
            "sensitive": True,
            "type": "file",
            "name": "service_account_json",
            "file_type": "application/json",  # this is used to filter the file type in the UI
        }
    )


class GcpmonitoringProvider(BaseProvider, ProviderHealthMixin):
    """Get alerts from GCP Monitoring into Keep."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure GCP Monitoring to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/gcpmonitoring-provider). 💡

To send alerts from GCP Monitoring to Keep, Use the following webhook url to configure GCP Monitoring send alerts to Keep:

1. In GCP Monitoring, go to Notification Channels.
2. In the Webhooks section click "ADD NEW".
3. In the Endpoint URL, configure:
- **Endpoint URL**: {keep_webhook_api_url}
- **Display Name**: keep-gcpmonitoring-webhook-integration
4. Click on "Use HTTP Basic Auth"
- **Auth Username**: api_key
- **Auth Password**: {api_key}
5. Click on "Save".
6. Go the the Alert Policy that you want to send to Keep and click on "Edit".
7. Go to "Notifications and name"
8. Click on "Notification Channels" and select the "keep-gcpmonitoring-webhook-integration" that you created in step 3.
9. Click on "SAVE POLICY".
"""

    # https://github.com/hashicorp/terraform-provider-google/blob/main/google/services/monitoring/resource_monitoring_alert_policy.go#L963
    SEVERITIES_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "ERROR": AlertSeverity.HIGH,
        "WARNING": AlertSeverity.WARNING,
    }
    PROVIDER_CATEGORY = ["Monitoring", "Cloud Infrastructure"]
    STATUS_MAP = {
        "CLOSED": AlertStatus.RESOLVED,
        "OPEN": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "GCP Monitoring"
    FINGERPRINT_FIELDS = ["incident_id"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="roles/logs.viewer",
            description="Read access to GCP logging",
            mandatory=True,
            alias="Logs Viewer",
        ),
    ]
    PROVIDER_METHODS = [
        ProviderMethod(
            name="query",
            func_name="execute_query",
            description="Query the GCP logs",
            type="view",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._service_account_data = json.loads(
            self.authentication_config.service_account_json
        )
        self._client = None

    def validate_config(self):
        self.authentication_config = GcpmonitoringProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        # try initializing the client to validate the scopes
        try:
            self.client.list_entries(max_results=1)
            scopes["roles/logs.viewer"] = True
        except google.api_core.exceptions.PermissionDenied:
            scopes["roles/logs.viewer"] = (
                "Permission denied, make sure IAM permissions are set correctly"
            )
        except Exception as e:
            scopes["roles/logs.viewer"] = str(e)
        return scopes

    @property
    def client(self) -> google.cloud.logging.Client:
        if self._client is None:
            self._client = self.__generate_client()
        return self._client

    def __generate_client(self) -> google.cloud.logging.Client:
        if not self._client:
            self._client = google.cloud.logging.Client.from_service_account_info(
                self._service_account_data
            )
        return self._client

    def execute_query(self, query: str, **kwargs):
        return self._query(query, **kwargs)

    def _query(
        self,
        filter: str,
        timedelta_in_days=1,
        page_size=1000,
        raw="true",
        project="",
        **kwargs,
    ):
        raw = raw == "true"
        self.logger.info(
            f"Querying GCP Monitoring with filter: {filter} and timedelta_in_days: {timedelta_in_days}"
        )
        if "timestamp" not in filter:
            start_time = (
                datetime.datetime.now(tz=datetime.timezone.utc)
                - datetime.timedelta(days=timedelta_in_days)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            filter = f'{filter} timestamp>="{start_time}"'

        if project:
            self.client.project = project

        entries_iterator = self.client.list_entries(filter_=filter, page_size=page_size)
        entries = []
        for entry in entries_iterator:
            if raw:
                entries.append(entry)
            else:
                try:
                    log_entry = LogEntry(
                        timestamp=entry.timestamp,
                        severity=entry.severity,
                        payload=entry.payload,
                        http_request=entry.http_request,
                        payload_exists=entry.payload is not None,
                        http_request_exists=entry.http_request is not None,
                    )
                    entries.append(log_entry)
                except Exception:
                    self.logger.error("Error parsing log entry")
                    continue

        self.logger.info(f"Found {len(entries)} entries")
        return entries

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        incident = event.get("incident", {})
        description = incident.pop("summary", "")
        status = GcpmonitoringProvider.STATUS_MAP.get(
            incident.pop("state", "").upper(), AlertStatus.FIRING
        )
        url = incident.pop("url", "")
        documentation = incident.pop("documentation", {})
        if isinstance(documentation, dict):
            name = (
                documentation.get("subject", description)
                or "GCPMontirong Alert (No subject)"
            )
        else:
            name = "Test notification"

        content = documentation.get("content", "")
        incident_id = incident.get("incident_id", "")
        # Get the severity
        if "severity" in incident:
            severity = GcpmonitoringProvider.SEVERITIES_MAP.get(
                incident.pop("severity").upper(), AlertSeverity.INFO
            )
        # In some cases (this is from the terraform provider) the severity is in the policy_user_labels
        else:
            severity = GcpmonitoringProvider.SEVERITIES_MAP.get(
                incident.get("policy_user_labels", {}).get("severity"),
                AlertSeverity.INFO,
            )
        # Parse and format the timestamp
        event_time = incident.get("started_at")
        if event_time:
            event_time = datetime.datetime.fromtimestamp(
                event_time, tz=datetime.timezone.utc
            )
            # replace timezone to utc

        else:
            event_time = datetime.datetime.now(tz=datetime.timezone.utc)

        event_time = event_time.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )

        policy_user_labels = incident.get("policy_user_labels", {})

        extra = {}
        if "service" in policy_user_labels:
            extra["service"] = policy_user_labels["service"]

        if "application" in policy_user_labels:
            extra["application"] = policy_user_labels["application"]

        # Construct the alert object
        alert = AlertDto(
            id=incident_id,
            name=name,
            status=status,
            lastReceived=event_time,
            source=["gcpmonitoring"],
            description=description,
            severity=severity,
            url=url,
            incident_id=incident_id,
            gcp=incident,  # rest of the fields
            content=content,
            **extra,
        )

        # Set fingerprint if applicable
        alert.fingerprint = BaseProvider.get_alert_fingerprint(
            alert, GcpmonitoringProvider.FINGERPRINT_FIELDS
        )
        return alert


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Get these from a secure source or environment variables
    with open("sa.json") as f:
        service_account_data = f.read()

    config = {
        "authentication": {
            "service_account_json": service_account_data,
        }
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="gcp-demo",
        provider_type="gcpmonitoring",
        provider_config=config,
    )
    entries = provider._query(
        filter='resource.type = "cloud_run_revision"',
        raw=False,
    )
    print(entries)
