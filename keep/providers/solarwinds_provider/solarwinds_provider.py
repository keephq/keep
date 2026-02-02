"""
Solarwinds Provider is a class that provides a way to receive alerts from Solarwinds using webhooks.
"""
import dataclasses
import pydantic
import requests
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    Authentication configuration for Solarwinds.
    """
    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Solarwinds Orion Host URL",
            "hint": "e.g. https://solarwinds.example.com",
            "sensitive": False,
        }
    )
    api_user: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Solarwinds API User",
            "sensitive": False,
        }
    )
    api_password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Solarwinds API Password",
            "sensitive": True,
        }
    )


class SolarwindsProvider(BaseProvider):
    """
    Get alerts from Solarwinds Orion into Keep via webhooks.
    """
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Solarwinds Orion to Keep:

1. Configure an alert action in Solarwinds Orion
2. Set webhook URL: {keep_webhook_api_url}
3. Add header "X-API-KEY" with your Keep API key
4. Configure alert triggers to send notifications
    """

    PROVIDER_DISPLAY_NAME = "Solarwinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_ICON = "solarwinds-icon.png"

    PROVIDER_SCOPES = [
        ProviderScope(name="read_alerts", description="Read alerts from Solarwinds"),
    ]

    # Solarwinds states Mapping to Keep alert states
    STATUS_MAP = {
        "Up": AlertStatus.RESOLVED,
        "Down": AlertStatus.FIRING,
        "Warning": AlertStatus.FIRING,
        "Critical": AlertStatus.FIRING,
        "Unmanaged": AlertStatus.RESOLVED,
        "Unplugged": AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        "Up": AlertSeverity.INFO,
        "Down": AlertSeverity.CRITICAL,
        "Warning": AlertSeverity.WARNING,
        "Critical": AlertSeverity.CRITICAL,
        "Unmanaged": AlertSeverity.INFO,
        "Unplugged": AlertSeverity.WARNING,
    }

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SolarwindsProviderAuthConfig(**self.config.authentication)

    def validate_scopes(self):
        return {"read_alerts": True}

    @staticmethod
    def _format_alert(event: dict, provider_instance: "BaseProvider" = None) -> AlertDto:
        """Format Solarwinds webhook payload into Keep alert format."""
        node_name = event.get("NodeName", "")
        alert_name = event.get("AlertName", "")
        status = event.get("Status", "Unknown")
        message = event.get("Message", "")
        
        return AlertDto(
            id=f"{node_name}:{alert_name}",
            name=alert_name or node_name,
            status=SolarwindsProvider.STATUS_MAP.get(status, AlertStatus.FIRING),
            severity=SolarwindsProvider.SEVERITY_MAP.get(status, AlertSeverity.INFO),
            description=message,
            source=["solarwinds"],
            hostname=node_name,
            status_text=status,
        )
