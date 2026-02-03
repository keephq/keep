from __future__ import annotations

import os
from uuid import uuid4
from typing import Any, Optional, Dict, List

from pydantic import BaseModel, Field as PydField, SecretStr, HttpUrl
from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB  # Optional; see notes below
from sqlalchemy import JSON as SA_JSON, Text as SA_Text
from sqlmodel import SQLModel, Field


# ----------------------------
# External AI definition (code-side)
# ----------------------------

class ExternalAI(BaseModel):
    """
    Base model for external algorithms (code-defined registry).
    """
    name: str
    description: str
    version: int = 1

    api_url: Optional[HttpUrl] = None
    api_key: Optional[SecretStr] = None

    # Store as a real python structure, not a JSON string.
    config_default: List[Dict[str, Any]] = PydField(default_factory=list)

    @property
    def unique_id(self) -> str:
        return f"{self.name}_{self.version}"


def _env_url(key: str) -> Optional[str]:
    v = os.environ.get(key)
    return v.strip() if v else None


def _env_secret(key: str) -> Optional[SecretStr]:
    v = os.environ.get(key)
    return SecretStr(v) if v else None


external_ai_transformers = ExternalAI(
    name="Transformers Correlation",
    description=(
        "A transformer-based alert-to-incident correlation algorithm, tailored per tenant. "
        "It associates new alerts with existing incidents if sufficiently similar; otherwise "
        "it creates new incidents."
    ),
    version=1,
    api_url=_env_url("KEEP_EXTERNAL_AI_TRANSFORMERS_URL"),
    api_key=_env_secret("KEEP_EXTERNAL_AI_TRANSFORMERS_API_KEY"),
    config_default=[
        {
            "min": 0.3,
            "max": 0.99,
            "value": 0.9,
            "type": "float",
            "name": "Model Accuracy Threshold",
            "description": (
                "Model accuracy evaluated with a 30% validation set. "
                "If below threshold, correlation won't launch."
            ),
        },
        {
            "min": 0.3,
            "max": 0.99,
            "value": 0.9,
            "type": "float",
            "name": "Correlation Threshold",
            "description": "Minimum correlation value to group alerts into an incident.",
        },
        {
            "min": 1,
            "max": 20,
            "value": 1,
            "type": "int",
            "name": "Train Epochs",
            "description": "Number of training epochs. Lower reduces overfitting risk.",
        },
        {
            "value": True,
            "type": "bool",
            "name": "Create New Incidents",
            "description": (
                "Create a new incident if correlation is detected but the related incident is resolved."
            ),
        },
        {
            "value": True,
            "type": "bool",
            "name": "Enabled",
            "description": "Enable or disable the algorithm.",
        },
    ],
)

EXTERNAL_AIS: List[ExternalAI] = [external_ai_transformers]
EXTERNAL_AI_BY_ID: Dict[str, ExternalAI] = {a.unique_id: a for a in EXTERNAL_AIS}


# ----------------------------
# DB model
# ----------------------------

class ExternalAIConfigAndMetadata(SQLModel, table=True):
    """
    Dynamic per-tenant algorithm settings and metadata.
    """

    __tablename__ = "external_ai_config"
    __table_args__ = (
        UniqueConstraint("tenant_id", "algorithm_id", name="uq_ext_ai_tenant_algo"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)

    tenant_id: str = Field(foreign_key="tenant.id", nullable=False, index=True)
    algorithm_id: str = Field(nullable=False, index=True, max_length=200)

    # Use JSON column, not a string pretending to be JSON.
    # If you are on Postgres, prefer JSONB. Otherwise SA_JSON is fine.
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SA_JSON, nullable=False),
    )

    settings_proposed_by_algorithm: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(SA_JSON, nullable=True),
    )

    feedback_logs: Optional[str] = Field(
        default=None,
        sa_column=Column(SA_Text, nullable=True),
    )

    @property
    def algorithm(self) -> Optional[ExternalAI]:
        # O(1) lookup instead of scanning the list every time.
        return EXTERNAL_AI_BY_ID.get(self.algorithm_id)

    @staticmethod
    def from_external_ai(tenant_id: str, algorithm: ExternalAI) -> "ExternalAIConfigAndMetadata":
        """
        Create a per-tenant config record seeded from the algorithm defaults.
        """
        return ExternalAIConfigAndMetadata(
            tenant_id=tenant_id,
            algorithm_id=algorithm.unique_id,
            # Store a structured JSON payload with versioned defaults.
            settings={
                "schema_version": 1,
                "controls": algorithm.config_default,
            },
        )