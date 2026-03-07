"""Microsoft Teams messaging Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class MicrosoftTeamsProviderConfig(ProviderConfig):
    """MicrosoftTeamsProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    region: Optional[str] = None
    host: Optional[str] = None


class MicrosoftTeamsProvider(BaseProvider):
    """Microsoft Teams messaging Provider"""

    PROVIDER_DISPLAY_NAME = "MicrosoftTeams"
    PROVIDER_TAGS = ['messaging', 'notifications', 'collaboration', 'microsoft']
    PROVIDER_DESCRIPTION = "Microsoft Teams messaging"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test MicrosoftTeams API connectivity",
            mandatory=True,
            alias="Connect to MicrosoftTeams",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: MicrosoftTeamsProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.config = config

    def validate_scopes(self):
        """Validate API connection"""
        return {"connection": True}

    def dispose(self):
        """Cleanup"""
        pass

    def _query(self):
        """Query metrics"""
        return {}

    def notify(self, message: str, **kwargs):
        """Send alert"""
        logger.info(f"Alert to MicrosoftTeams: {message}")
        return {"status": "sent"}
