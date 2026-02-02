"""
Nagios Provider is a class that provides a way to receive alerts from Nagios using webhooks.
"""
import dataclasses
import pydantic
import requests
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Authentication configuration for Nagios.
    """
    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Host URL",
            "hint": "e.g. https://nagios.example.com",
            "sensitive": False,
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "API Key for Nagios (optional)",
            "sensitive": True,
        }
    )


class NagiosProvider(BaseProvider):
    """
    Get alerts from Nagios into Keep via webhooks.
    """
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Nagios to Keep:

1. Install the notification script from Keep docs
2. Set webhook URL: {keep_webhook_api_url}
3. Add header "X-API-KEY" with your Keep API key
4. Configure Nagios notification commands
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_ICON = "nagios-icon.png"

    PROVIDER_SCOPES = [
        ProviderScope(name="read_alerts", description="Read alerts from Nagios"),
    ]

    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
    }

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(**self.config.authentication)

    def validate_scopes(self):
        return {"read_alerts": True}

    @staticmethod
    def _format_alert(event: dict, provider_instance: "BaseProvider" = None) -> AlertDto:
        """Format Nagios webhook payload into Keep alert format."""
        host = event.get("host", "")
        service = event.get("service", "")
        state = event.get("state", "UNKNOWN")
        output = event.get("output", "")
        
        return AlertDto(
            id=f"{host}:{service}" if service else host,
            name=service or host,
            status=NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING),
            severity=NagiosProvider.SEVERITY_MAP.get(state, AlertSeverity.INFO),
            description=output,
            source=["nagios"],
            hostname=host,
            service_name=service,
            state=state,
        )
