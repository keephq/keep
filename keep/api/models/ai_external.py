from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from keep.providers.models.provider_config import ProviderScope
from keep.providers.models.provider_method import ProviderMethod


class ExternalAIConfigAndMetadataDTO(BaseModel):
    algorithm_id: str
    tenant_id: str
    settings: str
    feedback_logs: str
    name: str
    description: str

