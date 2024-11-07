from datetime import datetime
from typing import Literal

from typing import Any
from pydantic import BaseModel, Json

from keep.api.models.db.ai_external import ExternalAI, ExternalAIConfigAndMetadata
from keep.providers.models.provider_config import ProviderScope
from keep.providers.models.provider_method import ProviderMethod


class ExternalAIDto(BaseModel):
    name: str
    description: str

    @classmethod
    def from_orm(cls, _object: ExternalAI) -> "ExternalAIDto":
        return cls(
            name=_object.name,
            description=_object.description
        )

class ExternalAIConfigAndMetadataDto(BaseModel):
    id: str
    algorithm_id: str
    tenant_id: str
    settings: Json[Any]
    feedback_logs: str | None
    algorithm: ExternalAIDto

    @classmethod
    def from_orm(cls, _object: ExternalAIConfigAndMetadata) -> "ExternalAIConfigAndMetadataDto":
        return cls(
            id=str(_object.id),
            algorithm_id=_object.algorithm_id,
            tenant_id=_object.tenant_id,
            settings=_object.settings,
            feedback_logs=_object.feedback_logs,
            algorithm=ExternalAIDto.from_orm(_object.algorithm)
        )

