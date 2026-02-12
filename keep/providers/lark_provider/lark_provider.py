"""
Lark (Feishu) Service Desk provider for Keep.
Supports webhook-based integration with Lark Service Desk for receiving ticket notifications.
"""

import dataclasses
import json
from typing import List, Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class LarkProviderAuthConfig:
    """Lark Service Desk authentication configuration."""
    
    app_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Lark App ID",
            "sensitive": False,
            "documentation_url": "https://open.feishu.cn/document/ukTMukTMukTM/ukzN3QjL5czN04SO3cDN",
        }
    )
    
    app_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Lark App Secret",
            "sensitive": True,
            "documentation_url": "https://open.feishu.cn/document/ukTMukTMukTM/ukzN3QjL5czN04SO3cDN",
        }
    )


class LarkProvider(BaseProvider):
    """Lark Service Desk provider for Keep."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="webhook",
            description="Webhook endpoint to receive Lark Service Desk notifications",
            mandatory=False,
            alias="Webhook",
        ),
    ]

    PROVIDER_TAGS = ["servicedesk", "ticketing", "collaboration"]
    SEVERITY_MAP = {
        "低": AlertSeverity.LOW,
        "中": AlertSeverity.MEDIUM,
        "高": AlertSeverity.HIGH,
        "紧急": AlertSeverity.CRITICAL,
        "low": AlertSeverity.LOW,
        "medium": AlertSeverity.MEDIUM,
        "high": AlertSeverity.HIGH,
        "critical": AlertSeverity.CRITICAL,
        "urgent": AlertSeverity.CRITICAL,
        "1": AlertSeverity.LOW,
        "2": AlertSeverity.MEDIUM,
        "3": AlertSeverity.HIGH,
        "4": AlertSeverity.CRITICAL,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self):
        """
        Validates that the user has the required scopes for the provider.
        """
        scopes = {}
        self.logger.info("Validating Lark Service Desk scopes")
        
        try:
            # Test API connectivity by attempting to get an access token
            self._get_access_token()
            scopes["webhook"] = True
        except Exception as e:
            self.logger.warning(f"Failed to validate Lark API access: {e}")
            scopes["webhook"] = False

        return scopes

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration fields.
        """
        self.authentication_config = LarkProviderAuthConfig(
            **self.config.authentication
        )

    def _get_access_token(self) -> str:
        """Get access token from Lark API."""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        
        payload = {
            "app_id": self.authentication_config.app_id,
            "app_secret": self.authentication_config.app_secret
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if result.get("code") != 0:
            raise Exception(f"Failed to get access token: {result.get('msg')}")
            
        return result.get("tenant_access_token")

    def _format_alert(self, event: dict, provider_instance: BaseProvider = None) -> AlertDto:
        """Convert Lark Service Desk event to AlertDto."""
        
        # Extract basic event information
        ticket_id = event.get("ticket_id", "unknown")
        ticket_title = event.get("title", event.get("summary", "Lark Service Desk Notification"))
        event_type = event.get("event_type", "ticket_update")
        
        # Map severity
        priority = event.get("priority", event.get("urgency", "medium")).lower()
        severity = self.SEVERITY_MAP.get(priority, AlertSeverity.MEDIUM)
        
        # Determine status
        ticket_status = event.get("status", "open").lower()
        status_mapping = {
            "open": "firing",
            "pending": "pending", 
            "resolved": "resolved",
            "closed": "resolved",
            "in_progress": "firing",
            "waiting": "pending"
        }
        status = status_mapping.get(ticket_status, "firing")
        
        # Build alert description
        description_parts = []
        if event.get("description"):
            description_parts.append(event["description"])
        if event.get("assignee"):
            description_parts.append(f"Assignee: {event['assignee']}")
        if event.get("category"):
            description_parts.append(f"Category: {event['category']}")
        
        description = "\n".join(description_parts) if description_parts else ticket_title
        
        # Extract labels
        labels = {
            "provider": "lark",
            "ticket_id": str(ticket_id),
            "event_type": event_type,
            "status": ticket_status,
        }
        
        # Add optional labels
        if event.get("category"):
            labels["category"] = event["category"]
        if event.get("assignee"):
            labels["assignee"] = event["assignee"]
        if event.get("requester"):
            labels["requester"] = event["requester"]
        
        return AlertDto(
            id=f"lark-{ticket_id}-{event_type}",
            name=ticket_title,
            status=status,
            severity=severity,
            description=description,
            source=["lark"],
            labels=labels,
            **event,  # Include all original event data
        )

    def _notify(self, **kwargs) -> None:
        """
        Send notifications to Lark Service Desk.
        Currently not implemented as this is primarily a webhook receiver.
        """
        self.logger.warning("Lark provider notification sending not implemented")
        pass

    @staticmethod
    def format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | List[AlertDto]:
        """
        Format a Lark Service Desk event into an AlertDto.
        
        Args:
            event (dict): The Lark Service Desk event
            provider_instance: The provider instance
            
        Returns:
            AlertDto: Formatted alert
        """
        if not provider_instance:
            # Create a minimal provider instance for formatting
            provider_instance = LarkProvider(
                context_manager=None,
                provider_id="lark",
                config=ProviderConfig(
                    authentication={},
                    name="lark"
                )
            )
            
        return provider_instance._format_alert(event)


if __name__ == "__main__":
    # Test the provider
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    context_manager = ContextManager(
        tenant_id="test",
        workflow_id="test",
    )
    
    # Test event data
    test_event = {
        "ticket_id": "TICKET-123",
        "title": "System Performance Issue",
        "description": "Database response times are degraded",
        "priority": "high",
        "status": "open",
        "category": "Infrastructure",
        "assignee": "john.doe@company.com",
        "requester": "user@company.com",
        "event_type": "ticket_created"
    }
    
    # Format the alert
    provider = LarkProvider(
        context_manager=context_manager,
        provider_id="test-lark",
        config=ProviderConfig(
            authentication={
                "app_id": "test_app_id",
                "app_secret": "test_secret"
            },
            name="test-lark"
        )
    )
    
    alert = provider._format_alert(test_event)
    print("Formatted Alert:")
    print(f"ID: {alert.id}")
    print(f"Name: {alert.name}")
    print(f"Severity: {alert.severity}")
    print(f"Status: {alert.status}")
    print(f"Labels: {alert.labels}")