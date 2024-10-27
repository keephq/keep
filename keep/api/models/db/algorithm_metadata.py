import os
import enum
import logging
import json
from typing import Optional
from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mssql import DATETIME2 as MSSQL_DATETIME2
from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
from sqlalchemy.engine.url import make_url
from sqlalchemy_utils import UUIDType
from sqlmodel import JSON, TEXT, Column, DateTime, Field, Index, Relationship, SQLModel

from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.config import config
from keep.api.models.alert import IncidentSeverity, IncidentStatus
from keep.api.models.db.tenant import Tenant
from enum import Enum, IntEnum
from pydantic import BaseModel, Json

from pydantic import BaseModel


class ExternalAI(BaseModel):
    """
    Base model for external algorithms.
    """
    name: str = None
    version: int = None
    api_url: str = None
    config_default: Json = None

    @property
    def unique_id(self):
        return self.name + "_" + str(self.version)


# Not sure if we'll need to move algorithm objects to the DB, 
# for now while we don't have a lot of them, it's ok to keep them as code.
TransformersAlgorithm = ExternalAI(
    name="transformers",
    version=1,
    api_url=os.environ.get("AI_TRANSFORMERS_API_HOST", "localhost:8082"),
    config_default=json.dumps({"threshold": {"min": 0.3, "max": 0.99, "value": 0.8, "type": "float"}})
)

AI_ALGORYTHMS = [
    TransformersAlgorithm
]

class AIConfigAndMetadata(SQLModel, table=True):
    """
    Dynamic per-tenant algo settings and metadata
    """
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    algorithm_id: str = Field(nullable=False)
    tenant_id: str = Field(ForeignKey("tenant.id"), nullable=False)
    settings: str = Field(nullable=False)
    feedback_logs: str = Field(nullable=True)

    @property
    def algorithm(self) -> ExternalAI:
        return [algo for algo in AI_ALGORYTHMS if algo.unique_id == self.algorithm_id][0]
    
    def from_external_ai(tenant_id: str, algorithm: ExternalAI):
        return AIConfigAndMetadata(
            algorithm_id=algorithm.unique_id,
            tenant_id=tenant_id,
            settings=json.dumps(algorithm.config_default),
        )
