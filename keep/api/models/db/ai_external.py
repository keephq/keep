import os
import requests
import json
import logging
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
    description: str = None
    version: int = None
    api_url: str = None
    api_key: str = None
    config_default: Json = None

    @property
    def unique_id(self):
        return self.name + "_" + str(self.version)
    

# Not sure if we'll need to move algorithm objects to the DB, 
# for now, it's ok to keep them as code.
external_ai_transformers = ExternalAI(
    name="Transformers Correlation",
    description="""A transformer-based alert-to-incident correlation algorithm, 
tailored for each tenant by training on their specific alert and incident data. 
The system will automatically associate new alerts with existing incidents if they are 
sufficiently similar; otherwise, it will create new incidents. In essence, it behaves like a human, 
analyzing the alert feed and making decisions for each incoming alert.""",
    version=1,
    api_url=os.environ.get("KEEP_EXTERNAL_AI_TRANSFORMERS_URL", None),
    api_key=os.environ.get("KEEP_EXTERNAL_AI_TRANSFORMERS_API_KEY", None),
    config_default=json.dumps(
        [
            {"min": 0.3, "max": 0.99, "value": 0.9, "type": "float", "name": "Model Accuracy Threshold", "description": "The trained model accuracy will be evaluated using 30 percent of alerts-to-incident correlations as a validation dataset. If the accuracy is below this threshold, the correlation won't be launched."},
            {"min": 0.3, "max": 0.99, "value": 0.9, "type": "float", "name": "Correlation Threshold", "description": "The minimum correlation value to consider two alerts belonging to an ancident."},
            {"min": 1, "max": 20, "value": 1, "type": "int", "name": "Train Epochs", "description": "The amount of epochs to train the model for. The less the better to avoid over-fitting."},
            {"value": True, "type": "bool", "name": "Create New Incidents", "description": "Do you want AI to issue new incident if correlation is detected and the incnident alerts are related to is resolved?"},
            {"value": True, "type": "bool", "name": "Enabled", "description": "Enable or disable the algorithm."},
        ]
    )
)

EXTERNAL_AIS = [
    external_ai_transformers
]

class ExternalAIConfigAndMetadata(SQLModel, table=True):
    """
    Dynamic per-tenant algo settings and metadata
    """
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    algorithm_id: str = Field(nullable=False)
    tenant_id: str = Field(ForeignKey("tenant.id"), nullable=False)
    settings: str = Field(nullable=False)
    settings_proposed_by_algorithm: str = Field(nullable=True)
    feedback_logs: str = Field(nullable=True)

    @property
    def algorithm(self) -> ExternalAI:
        matching_algos = [algo for algo in EXTERNAL_AIS if algo.unique_id == self.algorithm_id]
        return matching_algos[0] if len(matching_algos) > 0 else None
    
    def from_external_ai(tenant_id: str, algorithm: ExternalAI):
        external_ai = ExternalAIConfigAndMetadata(
            algorithm_id=algorithm.unique_id,
            tenant_id=tenant_id,
            settings=json.dumps(algorithm.config_default),
        )
        return external_ai
