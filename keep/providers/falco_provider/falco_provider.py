"""
Falco Provider is a class that provides a way to receive security alerts from Falco.
"""

import dataclasses
import logging
import pydantic
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class FalcoProviderAuthConfig:
    """
    Allows configuration for Falco provider.
    Since Falco pushes alerts via webhook, this config is mostly for UI representation
    and potentially fetching logs if a Falco Sidekick or API is present.
    """

    # For now, Falco integration is push-based (webhooks)
    # but we can add host_url if we want to query a FalcoSidekick API later.
    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        default="https://falco.example.com",
        metadata={
            "required": False,
            "description": "Falco/Sidekick URL (Optional)",
            "hint": "Used for deep links to events",
        }
    )


class FalcoProvider(BaseProvider):
    """
    Receive runtime security alerts from Falco into Keep.

    feat:
    - Webhook integration for real-time security events
    - Mapping Falco priorities to Keep severity
    - Container and Kubernetes context extraction
    """

    PROVIDER_DISPLAY_NAME = "Falco"
    PROVIDER_TAGS = ["security", "kubernetes", "runtime"]
    PROVIDER_CATEGORY = ["Security"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_ICON = "falco-icon.png"

    # Falco Priorities: Emergency, Alert, Critical, Error, Warning, Notice, Informational, Debug
    SEVERITY_MAP = {
        "Emergency": AlertSeverity.CRITICAL,
        "Alert": AlertSeverity.CRITICAL,
        "Critical": AlertSeverity.CRITICAL,
        "Error": AlertSeverity.CRITICAL,
        "Warning": AlertSeverity.WARNING,
        "Notice": AlertSeverity.INFO,
        "Informational": AlertSeverity.INFO,
        "Debug": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FalcoProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        # Webhook providers are generally considered valid if config parses
        return {"webhook": True}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format Falco JSON payload into Keep alert format.
        Expected Falco payload:
        {
            "output": "10:20:30.123456789: Critical Shell configuration file has been modified...",
            "priority": "Critical",
            "rule": "Modify Shell Configuration File",
            "time": "2026-02-11T07:30:00.000000000Z",
            "output_fields": {
                "container.id": "abc123",
                "k8s.pod.name": "my-pod",
                "user.name": "root",
                ...
            }
        }
        """
        priority = event.get("priority", "Informational")
        output_fields = event.get("output_fields", {})
        
        alert = AlertDto(
            id=event.get("rule", "falco-security-event"),
            name=event.get("rule", "Falco Rule Triggered"),
            status=AlertStatus.FIRING,
            severity=FalcoProvider.SEVERITY_MAP.get(priority, AlertSeverity.INFO),
            timestamp=event.get("time"),
            description=event.get("output"),
            source=["falco"],
            hostname=output_fields.get("container.id") or output_fields.get("host.hostname"),
            service_name=output_fields.get("k8s.pod.name"),
            # Dynamic attributes for security forensics
            user=output_fields.get("user.name"),
            container_id=output_fields.get("container.id"),
            pname=output_fields.get("proc.name"),
        )
        return alert


if __name__ == "__main__":
    pass
