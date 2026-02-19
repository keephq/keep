"""
SolarwindsProvider is a class that implements the BaseProvider interface for SolarWinds Orion updates.
"""
import dataclasses
import requests
from typing import List, Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
import pydantic

@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """SolarWinds authentication configuration."""
    hostname: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Hostname/IP",
            "sensitive": False,
            "hint": "orion.example.com",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Username",
            "sensitive": False,
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Password",
            "sensitive": True,
        }
    )
    port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "SolarWinds API Port (default 17778)",
            "sensitive": False,
        },
        default=17778,
    )

class SolarwindsProvider(BaseProvider):
    """SolarWinds Orion Provider."""
    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["monitoring"]
    PROVIDER_CATEGORY = ["Monitoring"]
    
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read",
            description="Read from SolarWinds Orion",
            mandatory=True,
            alias="Read access",
        )
    ]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def _notify(self, title: str, message: str, **kwargs):
        """
        SolarWinds notification typically means creating an event or acknowledge an alert.
        For now, we'll implement a simple event logging if needed, or placeholder for alert suppression.
        """
        self.logger.info(f"SolarWinds notify called: {title}")
        return {"success": True}

    def _query(self, query: str, **kwargs):
        """
        Query SolarWinds via SWQL.
        """
        url = f"https://{self.authentication_config.hostname}:{self.authentication_config.port}/SolarWinds/InformationService/v3/Json/Query"
        try:
            response = requests.post(
                url,
                json={"query": query, "parameters": kwargs.get("parameters", {})},
                auth=(self.authentication_config.username, self.authentication_config.password),
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception as e:
            raise ProviderException(f"SolarWinds query failed: {e}")

    def get_alerts(self) -> List[dict]:
        """
        Fetch active alerts from SolarWinds Orion.
        """
        swql_query = """
            SELECT 
                AlertActiveID, 
                AlertObjectName, 
                EntityCaption, 
                EntityNetObjectID, 
                RelatedNodeCaption, 
                TriggeredDateTime, 
                TriggeredMessage, 
                Severity
            FROM Orion.AlertActive
        """
        results = self._query(swql_query)
        return results

    def validate_scopes(self):
        try:
            # Simple query to validate connection and permissions
            self._query("SELECT TOP 1 NodeID FROM Orion.Nodes")
            return {"read": True}
        except Exception as e:
            return {"read": str(e)}

    def dispose(self):
        pass
