"""PlayStation Network gaming provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PSNProviderAuthConfig:
    npsso: str = dataclasses.field(
        metadata={"required": True, "description": "PlayStation NPSSO Token", "sensitive": True},
        default=""
    )

class PSNProvider(BaseModel):
    """PlayStation Network gaming provider."""
    
    PROVIDER_DISPLAY_NAME = "PlayStation Network"
    PROVIDER_CATEGORY = ["Gaming"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PSNProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, psn_id: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not psn_id or not message:
            raise ProviderException("PSN ID and message are required")

        self.logger.info(f"PlayStation notification for {psn_id}")
        return {"status": "success", "psn_id": psn_id}
