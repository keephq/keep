"""
Falco is an open-source runtime security engine that detects anomalous activity in containers, Kubernetes, and hosts.
"""

import logging
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class FalcoProvider(BaseProvider):
    """Receive security alerts from Falco via webhook."""

    PROVIDER_DISPLAY_NAME = "Falco"
    PROVIDER_CATEGORY = ["Security", "Monitoring"]
    PROVIDER_TAGS = ["alert", "security", "runtime", "cncf"]
    FINGERPRINT_FIELDS = ["rule", "hostname", "output_fields"]

    webhook_description = "Receive Falco security alerts via webhook"
    webhook_template = ""
    webhook_markdown = """
    To configure Falco to send alerts to Keep:

    1. Install and configure [Falcosidekick](https://github.com/falcosecurity/falcosidekick) (recommended) or use Falco's built-in HTTP output.

    2. **Using Falcosidekick (Recommended):**
       
       Set the following environment variables or configuration:
       ```yaml
       webhook:
         address: "{keep_webhook_api_url}"
         method: "POST"
         headers:
           X-API-KEY: "{api_key}"
           Content-Type: "application/json"
       ```

    3. **Using Falco's native HTTP output:**
       
       Add to your `falco.yaml`:
       ```yaml
       http_output:
         enabled: true
         url: "{keep_webhook_api_url}"
         user_agent: "falcosecurity/falco"
       ```

    4. Restart Falco/Falcosidekick.

    For more details, see the [Falco documentation](https://falco.org/docs/outputs/forwarding/).
    """

    SEVERITIES_MAP = {
        "EMERGENCY": AlertSeverity.CRITICAL,
        "ALERT": AlertSeverity.CRITICAL,
        "CRITICAL": AlertSeverity.CRITICAL,
        "ERROR": AlertSeverity.HIGH,
        "WARNING": AlertSeverity.WARNING,
        "WARN": AlertSeverity.WARNING,
        "NOTICE": AlertSeverity.INFO,
        "INFORMATIONAL": AlertSeverity.INFO,
        "DEBUG": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        No validation required for Falco webhook provider.
        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format Falco webhook payload into Keep AlertDto.
        
        Falco webhook payload format (via Falcosidekick):
        {
            "output": "12:34:56.789123789: Notice A shell was spawned...",
            "priority": "Notice",
            "rule": "Terminal shell in container",
            "time": "2024-01-15T12:34:56.789123789Z",
            "output_fields": {
                "container.id": "docker://abc123",
                "container.name": "myapp",
                "evt.time": 1705325696789123789,
                "k8s.ns.name": "default",
                "k8s.pod.name": "myapp-xyz",
                "proc.name": "bash",
                "user.name": "root"
            },
            "hostname": "worker-node-1",
            "tags": ["container", "shell", "mitre_execution"]
        }
        """
        logger.info(f"Formatting Falco alert: {event}")

        # Extract priority and map to severity
        priority = event.get("priority", "NOTICE").upper()
        severity = FalcoProvider.SEVERITIES_MAP.get(priority, AlertSeverity.INFO)

        # Parse timestamp
        time_str = event.get("time")
        if time_str:
            try:
                # Falco sends ISO8601 format
                last_received = datetime.fromisoformat(time_str.replace('Z', '+00:00')).isoformat()
            except (ValueError, TypeError):
                logger.warning(f"Failed to parse Falco time: {time_str}")
                last_received = datetime.now(timezone.utc).isoformat()
        else:
            last_received = datetime.now(timezone.utc).isoformat()

        # Extract output fields
        output_fields = event.get("output_fields", {})
        
        # Build tags list
        tags = event.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        
        # Add Falco-specific context as labels
        labels = {
            "falco_rule": event.get("rule", ""),
            "falco_priority": priority,
        }
        
        # Add Kubernetes context if available
        if "k8s.ns.name" in output_fields:
            labels["k8s_namespace"] = output_fields["k8s.ns.name"]
        if "k8s.pod.name" in output_fields:
            labels["k8s_pod"] = output_fields["k8s.pod.name"]
        if "k8s.node.name" in output_fields:
            labels["k8s_node"] = output_fields["k8s.node.name"]
            
        # Add container context if available
        if "container.name" in output_fields:
            labels["container_name"] = output_fields["container.name"]
        if "container.id" in output_fields:
            labels["container_id"] = output_fields["container.id"]
            
        # Add process context if available
        if "proc.name" in output_fields:
            labels["process_name"] = output_fields["proc.name"]
        if "proc.cmdline" in output_fields:
            labels["process_cmdline"] = output_fields["proc.cmdline"]
        if "user.name" in output_fields:
            labels["user_name"] = output_fields["user.name"]

        # Create unique ID from rule, hostname and timestamp
        rule = event.get("rule", "Unknown")
        hostname = event.get("hostname", "unknown")
        alert_id = f"{rule}:{hostname}:{last_received}"

        alert = AlertDto(
            id=alert_id,
            name=rule,
            description=event.get("output", ""),
            severity=severity,
            status=AlertStatus.FIRING,
            source=["falco"],
            hostname=hostname,
            output_fields=output_fields,
            tags=tags,
            labels=labels,
            lastReceived=last_received,
        )

        return alert


if __name__ == "__main__":
    pass
