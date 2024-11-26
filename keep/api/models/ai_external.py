import os
import logging
import requests

from typing import Any
from dataclasses import Field
from datetime import datetime

from pydantic import BaseModel, Json, Field

from keep.api.models.db.ai_external import ExternalAI, ExternalAIConfigAndMetadata


logger = logging.getLogger(__name__)


class ExternalAIDto(BaseModel):
    name: str
    description: str

    last_time_reminded: datetime | None = None

    api_url: str | None = Field(exclude=True)
    api_key: str | None = Field(exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.last_time_reminded = None

    @classmethod
    def from_orm(cls, _object: ExternalAI) -> "ExternalAIDto":
        return cls(
            name=_object.name,
            description=_object.description,
            api_url=_object.api_url,
            api_key=_object.api_key,
        )
    
    def remind_about_the_client(self, tenant_id: str):
        """
        AI services are stateless by design, 
        so we need to remind about the client each time we want them to be executed.
        """
        from keep.api.utils.tenant_utils import get_or_create_api_key
        from keep.api.core.db import get_session

        if self.last_time_reminded and (datetime.now() - self._last_time_reminded).total_seconds() < 30:
            logger.info(f"Skipping reminder about the client for {self.name} as it was reminded recently.")
            return
        else:
            self.last_time_reminded = datetime.now()

        self.last_time_reminded = datetime.now()
        back_api_key = get_or_create_api_key(
            session=next(get_session()),
            tenant_id=tenant_id, 
            created_by="system",
            unique_api_key_id=self.name
        )
        
        try:
            response = requests.post(
                self.api_url + "/remind_about_the_client",
                json={
                    "api_key": self.api_key,
                    "tenant_id": tenant_id, 
                    "back_api_key": back_api_key,
                    "back_api_url": os.environ.get("KEEP_API_URL"),
                },
                timeout=0.5  # 1 second timeout, intentionally short because it's blocking and we don't care about response.
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to remind about the client for {self.name}. Error: {e}")
            return
        

class ExternalAIConfigAndMetadataDto(BaseModel):
    id: str
    algorithm_id: str
    tenant_id: str
    settings: list[Any] | Json[Any]
    settings_proposed_by_algorithm: list[Any] | Json[Any] | None
    feedback_logs: str | None
    algorithm: ExternalAIDto

    @classmethod
    def from_orm(cls, _object: ExternalAIConfigAndMetadata) -> "ExternalAIConfigAndMetadataDto":
        return cls(
            id=str(_object.id),
            algorithm_id=_object.algorithm_id,
            tenant_id=_object.tenant_id,
            settings=_object.settings,
            settings_proposed_by_algorithm=_object.settings_proposed_by_algorithm,
            feedback_logs=_object.feedback_logs,
            algorithm=ExternalAIDto.from_orm(_object.algorithm)
        )
