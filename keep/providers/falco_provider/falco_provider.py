"""
Falco Provider is a class that allows to ingest alerts from Falco,
a cloud-native runtime security tool by CNCF.

Falco detects threats in real-time across containers, Kubernetes, hosts,
and cloud services. This provider receives webhook alerts from Falco's
built-in HTTP output or from Falcosidekick.
"""

import datetime
import hashlib
import logging

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class FalcoProvider(BaseProvider):
    """Receive runtime security alerts from Falco via webhook."""

    PROVIDER_DISPLAY_NAME = "Falco"
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "Security"]
    PROVIDER_TAGS = ["alert", "security"]
    FINGERPRINT_FIELDS = ["rule", "hostname", "source"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure Falco to send alerts to Keep, see the
[Falco Output Channels documentation](https://falco.org/docs/outputs/channels/).

## Option 1: Falco HTTP Output (Direct)

Configure Falco to send alerts directly via its built-in HTTP output:

1. Edit your Falco configuration file (`/etc/falco/falco.yaml`).
2. Enable JSON output and the HTTP output channel:
    ```yaml
    json_output: true
    json_include_output_property: true
    json_include_tags_property: true

    http_output:
      enabled: true
      url: {keep_webhook_api_url}
      headers:
        x-api-key: {api_key}
    ```
3. Restart Falco.

## Option 2: Falcosidekick (Recommended)

Use [Falcosidekick](https://github.com/falcosecurity/falcosidekick) for more flexible alert routing:

1. Deploy Falcosidekick alongside Falco.
2. Configure a webhook output in Falcosidekick's config:
    ```yaml
    webhook:
      address: {keep_webhook_api_url}
      customHeaders:
        x-api-key: {api_key}
    ```
3. Point Falco's `http_output.url` to Falcosidekick.
"""

    # Map Falco priority levels to Keep AlertSeverity.
    # Falco priorities: Emergency, Alert, Critical, Error, Warning, Notice,
    #                   Informational, Debug
    SEVERITIES_MAP = {
        "emergency": AlertSeverity.CRITICAL,
        "alert": AlertSeverity.CRITICAL,
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "notice": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """No authentication config required – this is a webhook-only provider."""
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Falco alert event into a Keep AlertDto.

        Falco JSON payload fields:
            - rule: str – name of the triggered rule
            - priority: str – severity level (Emergency … Debug)
            - output: str – formatted human-readable message
            - output_fields: dict – structured fields from the event
            - time: str – ISO 8601 timestamp
            - source: str – event source (e.g. "syscall", "k8s_audit")
            - tags: list[str] – rule tags (e.g. "container", "mitre_execution")
            - hostname: str – host where Falco is running
            - uuid: str – optional unique event ID (falcosidekick)
        """

        rule = event.get("rule", "Unknown Falco Rule")
        priority = event.get("priority", "warning").lower()
        output = event.get("output", "")
        output_fields = event.get("output_fields") or {}
        falco_time = event.get("time", "")
        source = event.get("source", "")
        tags = event.get("tags") or []
        hostname = event.get("hostname", "")
        uuid = event.get("uuid", "")

        # Map severity
        severity = FalcoProvider.SEVERITIES_MAP.get(
            priority, AlertSeverity.INFO
        )

        # Parse timestamp
        last_received = falco_time
        if not last_received:
            last_received = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()

        # Build a stable fingerprint from rule + hostname + source
        fingerprint_source = f"{rule}|{hostname}|{source}"
        fingerprint = hashlib.sha256(fingerprint_source.encode()).hexdigest()

        # Use the uuid from falcosidekick if available, otherwise derive one
        alert_id = uuid if uuid else fingerprint

        # Extract container / k8s metadata from output_fields
        container_id = output_fields.get("container.id", "")
        container_name = output_fields.get("container.name", "")
        container_image = output_fields.get(
            "container.image.repository", ""
        ) or output_fields.get("container.image", "")
        k8s_namespace = output_fields.get("k8s.ns.name", "")
        k8s_pod = output_fields.get("k8s.pod.name", "")
        user = output_fields.get("user.name", "")
        process = output_fields.get("proc.name", "")
        cmdline = output_fields.get("proc.cmdline", "")

        # Build description with available metadata
        description_parts = [output]
        if container_name:
            description_parts.append(f"Container: {container_name}")
        if k8s_namespace and k8s_pod:
            description_parts.append(f"K8s: {k8s_namespace}/{k8s_pod}")
        if container_image:
            description_parts.append(f"Image: {container_image}")
        description = " | ".join(
            [p for p in description_parts if p]
        )

        # Track which output_fields have been consumed for labels
        consumed_fields = {
            "container.id",
            "container.name",
            "container.image.repository",
            "container.image",
            "k8s.ns.name",
            "k8s.pod.name",
            "user.name",
            "proc.name",
            "proc.cmdline",
        }

        # Build labels from tags and metadata
        labels = {}
        if tags:
            labels["tags"] = ", ".join(tags)
        if source:
            labels["source"] = source
        if hostname:
            labels["hostname"] = hostname
        if container_id:
            labels["container_id"] = container_id
        if container_name:
            labels["container_name"] = container_name
        if container_image:
            labels["container_image"] = container_image
        if k8s_namespace:
            labels["k8s_namespace"] = k8s_namespace
        if k8s_pod:
            labels["k8s_pod"] = k8s_pod
        if user:
            labels["user"] = user
        if process:
            labels["process"] = process
        if cmdline:
            labels["cmdline"] = cmdline

        # Determine service from k8s pod / container name
        service = k8s_pod or container_name or hostname or None

        # Include remaining output_fields in labels so nothing is lost
        for key, value in output_fields.items():
            if key not in consumed_fields:
                # Use underscored key to keep label names consistent
                label_key = key.replace(".", "_")
                if label_key not in labels:
                    labels[label_key] = (
                        str(value) if value is not None else ""
                    )

        return AlertDto(
            id=alert_id,
            name=rule,
            status=AlertStatus.FIRING,
            severity=severity,
            lastReceived=last_received,
            description=description,
            source=["falco"],
            message=output,
            pushed=True,
            fingerprint=fingerprint,
            service=service,
            environment=k8s_namespace if k8s_namespace else "undefined",
            labels=labels,
        )


if __name__ == "__main__":
    pass
