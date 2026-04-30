"""
Coroot Provider is a class that allows to receive alerts from Coroot.

Coroot is an open-source observability platform for microservices that provides
eBPF-based monitoring, distributed tracing, and SLO-based alerting.
"""

import hashlib
from typing import Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class CorootProvider(BaseProvider):
    """Receive alerts from Coroot into Keep."""

    PROVIDER_DISPLAY_NAME = "Coroot"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_COMING_SOON = False

    webhook_description = "Receive alerts from Coroot"
    webhook_template = ""
    webhook_markdown = """
## Coroot Webhook Integration

To send alerts from Coroot to Keep, configure a webhook integration in Coroot:

1. In Coroot, navigate to **Project Settings** → **Integrations**
2. Click on **Webhook** integration
3. Configure the webhook with the following settings:
   - **URL**: `{keep_webhook_api_url}`
   - **Method**: POST
4. Add an HTTP header:
   - **Key**: `x-api-key`
   - **Value**: `{api_key}`
5. Save the configuration

### Incident Notification Template

Use the following template for incident notifications:

```json
{{{{
  "status": "{{{{.Status}}}}",
  "application": {{{{
    "namespace": "{{{{.Application.Namespace}}}}",
    "kind": "{{{{.Application.Kind}}}}",
    "name": "{{{{.Application.Name}}}}"
  }}}},
  "reports": [
    {{{{range $i, $r := .Reports}}}}{{{{if $i}}}},{{{{end}}}}
    {{{{
      "name": "{{{{$r.Name}}}}",
      "check": "{{{{$r.Check}}}}",
      "message": "{{{{$r.Message}}}}"
    }}}}
    {{{{end}}}}
  ],
  "url": "{{{{.URL}}}}"
}}}}
```

### Deployment Notification Template (Optional)

```json
{{{{
  "type": "deployment",
  "status": "{{{{.Status}}}}",
  "application": {{{{
    "namespace": "{{{{.Application.Namespace}}}}",
    "kind": "{{{{.Application.Kind}}}}",
    "name": "{{{{.Application.Name}}}}"
  }}}},
  "version": "{{{{.Version}}}}",
  "summary": [{{{{range $i, $s := .Summary}}}}{{{{if $i}}}},{{{{end}}}}"{{{{$s}}}}"{{{{end}}}}],
  "url": "{{{{.URL}}}}"
}}}}
```

Coroot will now send alerts to Keep when incidents are detected based on SLO violations.
"""

    # Map Coroot status to Keep AlertStatus
    STATUS_MAP = {
        "ok": AlertStatus.RESOLVED,
        "OK": AlertStatus.RESOLVED,
        "warning": AlertStatus.FIRING,
        "WARNING": AlertStatus.FIRING,
        "critical": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        # Deployment statuses
        "Deployed": AlertStatus.RESOLVED,
        "Cancelled": AlertStatus.RESOLVED,
        "Stuck": AlertStatus.FIRING,
    }

    # Map Coroot status to Keep AlertSeverity
    SEVERITIES_MAP = {
        "ok": AlertSeverity.INFO,
        "OK": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "WARNING": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
        "CRITICAL": AlertSeverity.CRITICAL,
        # Deployment statuses
        "Deployed": AlertSeverity.INFO,
        "Cancelled": AlertSeverity.WARNING,
        "Stuck": AlertSeverity.HIGH,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Coroot provider.
        No configuration is required for webhook-only provider.
        """
        pass

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    @staticmethod
    def _generate_fingerprint(event: dict) -> str:
        """
        Generate a unique fingerprint for the alert based on application and reports.
        """
        application = event.get("application", {})
        reports = event.get("reports", [])

        # Build fingerprint from application identity and report checks
        fingerprint_parts = [
            application.get("namespace", ""),
            application.get("kind", ""),
            application.get("name", ""),
        ]

        # Add report checks to fingerprint for uniqueness
        for report in reports:
            fingerprint_parts.append(report.get("name", ""))
            fingerprint_parts.append(report.get("check", ""))

        fingerprint_string = "|".join(fingerprint_parts)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["BaseProvider"] = None
    ) -> AlertDto:
        """
        Format a Coroot webhook event into a Keep AlertDto.

        Coroot sends two types of notifications:
        1. Incident notifications with status (OK/WARNING/CRITICAL)
        2. Deployment notifications with status (Deployed/Cancelled/Stuck)
        """
        # Check if this is a deployment notification
        is_deployment = event.get("type") == "deployment" or "version" in event

        # Extract common fields
        status_str = event.get("status", "CRITICAL")
        application = event.get("application", {})
        url = event.get("url", "")

        # Build application identifier
        app_namespace = application.get("namespace", "")
        app_kind = application.get("kind", "")
        app_name = application.get("name", "unknown")

        # Map status and severity
        status = CorootProvider.STATUS_MAP.get(status_str, AlertStatus.FIRING)
        severity = CorootProvider.SEVERITIES_MAP.get(status_str, AlertSeverity.WARNING)

        # Generate fingerprint
        fingerprint = CorootProvider._generate_fingerprint(event)

        if is_deployment:
            # Handle deployment notification
            version = event.get("version", "")
            summary = event.get("summary", [])

            alert_name = f"Deployment: {app_name}"
            description = f"Deployment {status_str} for {app_name}"
            if version:
                description += f" (version: {version})"
            if summary:
                description += "\n" + "\n".join(summary)

            alert_dto = AlertDto(
                id=fingerprint,
                fingerprint=fingerprint,
                name=alert_name,
                status=status,
                severity=severity,
                description=description,
                source=["coroot"],
                url=url or None,
                # Coroot-specific fields
                namespace=app_namespace,
                application_kind=app_kind,
                application_name=app_name,
                deployment_version=version,
                deployment_summary=summary,
                event_type="deployment",
            )
        else:
            # Handle incident notification
            reports = event.get("reports", [])

            # Build alert name from reports
            if reports:
                report_names = [r.get("name", "") for r in reports if r.get("name")]
                checks = [r.get("check", "") for r in reports if r.get("check")]
                alert_name = f"{app_name}: {', '.join(checks)}" if checks else f"{app_name}: SLO Violation"
            else:
                alert_name = f"{app_name}: Incident"

            # Build description from report messages
            description_parts = []
            for report in reports:
                report_name = report.get("name", "")
                check = report.get("check", "")
                message = report.get("message", "")
                if message:
                    if report_name and check:
                        description_parts.append(f"[{report_name}/{check}] {message}")
                    else:
                        description_parts.append(message)

            description = "\n".join(description_parts) if description_parts else f"Incident detected for {app_name}"

            # Extract labels from reports
            labels = {}
            for i, report in enumerate(reports):
                if report.get("name"):
                    labels[f"report_{i}_name"] = report.get("name")
                if report.get("check"):
                    labels[f"report_{i}_check"] = report.get("check")

            alert_dto = AlertDto(
                id=fingerprint,
                fingerprint=fingerprint,
                name=alert_name,
                status=status,
                severity=severity,
                description=description,
                source=["coroot"],
                url=url or None,
                labels=labels,
                # Coroot-specific fields
                namespace=app_namespace,
                application_kind=app_kind,
                application_name=app_name,
                reports=reports,
                event_type="incident",
            )

        # Add environment from namespace if available
        if app_namespace:
            alert_dto.environment = app_namespace

        # Add service from application name
        if app_name:
            alert_dto.service = app_name

        return alert_dto


if __name__ == "__main__":
    # Test the provider with sample data
    import json

    # Sample incident notification
    incident_event = {
        "status": "CRITICAL",
        "application": {
            "namespace": "production",
            "kind": "Deployment",
            "name": "api-service",
        },
        "reports": [
            {
                "name": "SLO",
                "check": "Availability",
                "message": "error budget burn rate is 26x within 1 hour",
            },
            {
                "name": "Memory",
                "check": "Memory leak",
                "message": "app containers have been restarted 11 times by the OOM killer",
            },
        ],
        "url": "https://coroot.example.com/p/default/app/production/Deployment/api-service",
    }

    # Sample deployment notification
    deployment_event = {
        "type": "deployment",
        "status": "Deployed",
        "application": {
            "namespace": "production",
            "kind": "Deployment",
            "name": "api-service",
        },
        "version": "v1.2.3",
        "summary": [
            "Availability: 99.5% (objective: 99%)",
            "CPU usage: +5% (+$10/mo)",
        ],
        "url": "https://coroot.example.com/p/default/app/production/Deployment/api-service",
    }

    print("=== Incident Alert ===")
    alert = CorootProvider._format_alert(incident_event)
    print(f"Name: {alert.name}")
    print(f"Status: {alert.status}")
    print(f"Severity: {alert.severity}")
    print(f"Description: {alert.description}")
    print(f"Fingerprint: {alert.fingerprint}")

    print("\n=== Deployment Alert ===")
    alert = CorootProvider._format_alert(deployment_event)
    print(f"Name: {alert.name}")
    print(f"Status: {alert.status}")
    print(f"Severity: {alert.severity}")
    print(f"Description: {alert.description}")
