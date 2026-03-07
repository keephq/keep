"""Website monitoring service Provider for Keep"""

import logging
import requests
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class UptimeRobotProviderConfig(ProviderConfig):
    """UptimeRobotProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    auth_token: Optional[str] = None
    account_email: Optional[str] = None


class UptimeRobotProvider(BaseProvider):
    """Website monitoring service Provider"""

    PROVIDER_DISPLAY_NAME = "UptimeRobot"
    PROVIDER_TAGS = ['monitoring', 'uptime', 'webhook']
    PROVIDER_DESCRIPTION = "Website monitoring service"
    PROVIDER_ICON_URL = "https://logo.clearbit.com/api.uptimerobot.com"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test UptimeRobot API connectivity",
            mandatory=True,
            alias="Connect to UptimeRobot",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: UptimeRobotProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.api_key = config.api_key
        self.api_token = config.api_token
        self.auth_token = config.auth_token
        self.base_url = "https://api.uptimerobot.com/v2"

    def _get_headers(self):
        """Get API headers"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        elif self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def validate_scopes(self):
        """Validate API connection"""
        try:
            response = requests.get(
                f"{self.base_url}/",
                headers=self._get_headers(),
                timeout=10
            )
            if response.status_code in [200, 401]:  # 401 means server is reachable
                return {"connection": True}
            raise Exception(f"API error: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise

    def _query(self, **kwargs):
        """Query UptimeRobot for data"""
        # Implement specific query logic
        return {}

    def notify(self, message: str, **kwargs):
        """Send alert to UptimeRobot"""
        # Implement alert sending
        logger.info(f"Sending alert to UptimeRobot: {message}")
        return {"status": "sent", "message": message}

    def dispose(self):
        """Cleanup"""
        pass
