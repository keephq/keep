"""
Keep main database module.

This module contains the CRUD database functions for Keep.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, desc, func, select
from sqlmodel import Session

from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    PropertiesMetadata,
)
from keep.api.core.db import engine
from keep.api.models.db.facet import FacetType
from keep.api.models.db.workflow import Workflow, WorkflowExecution
from keep.api.models.facet import FacetDto


workflow_field_configurations = [
    FieldMappingConfiguration("source", "filter_provider_type"),
    FieldMappingConfiguration("providerId", "filter_provider_id"),
    FieldMappingConfiguration("providerType", "filter_provider_type"),
    FieldMappingConfiguration("lastReceived", "filter_last_received"),
    FieldMappingConfiguration("startedAt", "startedAt"),
    FieldMappingConfiguration(
        map_from_pattern="incident.name",
        map_to=[
            "filter_incident_user_generated_name",
            "filter_incident_ai_generated_name",
        ],
    ),
    FieldMappingConfiguration(
        map_from_pattern="severity",
        map_to=[
            "JSON(filter_alert_enrichment_json).*",
            "JSON(filter_alert_event_json).*",
        ],
        enum_values=[
            severity.value
            for severity in sorted(
                [severity for _, severity in enumerate(AlertSeverity)],
                key=lambda s: s.order,
            )
        ],
    ),
    FieldMappingConfiguration(
        map_from_pattern="status",
        map_to=[
            "JSON(filter_alert_enrichment_json).*",
            "JSON(filter_alert_event_json).*",
        ],
        enum_values=list(reversed([item.value for _, item in enumerate(AlertStatus)])),
    ),
    FieldMappingConfiguration(
        map_from_pattern="*",
        map_to=[
            "JSON(filter_alert_enrichment_json).*",
            "JSON(filter_alert_event_json).*",
        ],
    ),
]
alias_column_mapping = {
    "filter_last_received": "alert.timestamp",
    "filter_provider_id": "alert.provider_id",
    "filter_provider_type": "alert.provider_type",
    "filter_incident_user_generated_name": "incident.user_generated_name",
    "filter_incident_ai_generated_name": "incident.ai_generated_name",
    "filter_alert_enrichment_json": "alertenrichment.enrichments",
    "filter_alert_event_json": "alert.event",
}

properties_metadata = PropertiesMetadata(workflow_field_configurations)

static_facets = [
    FacetDto(
        id="f8a91ac7-4916-4ad0-9b46-a5ddb85bfbb8",
        property_path="severity",
        name="Severity",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="5dd1519c-6277-4109-ad95-c19d2f4f15e3",
        property_path="status",
        name="Status",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="461bef05-fc20-4363-b427-9d26fe064e7f",
        property_path="source",
        name="Source",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="6afa12d7-21df-4694-8566-fd56d5ee2266",
        property_path="incident.name",
        name="Incident",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="77b8a6d4-3b8d-4b6a-9f8e-2c8e4b8f8e4c",
        property_path="dismissed",
        name="Dismissed",
        is_static=True,
        type=FacetType.str,
    ),
]
static_facets_dict = {facet.id: facet for facet in static_facets}


def get_workflows_with_last_executions_v2(
    tenant_id: str,
    cel: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_dir: str,
    fetch_last_executions: int = 15,
) -> list[dict]:
    if fetch_last_executions is not None and fetch_last_executions > 20:
        fetch_last_executions = 20

    # List first 1000 worflows and thier last executions in the last 7 days which are active)
    with Session(engine) as session:
        latest_executions_subquery = (
            select(
                WorkflowExecution.workflow_id,
                WorkflowExecution.started,
                WorkflowExecution.execution_time,
                WorkflowExecution.status,
                func.row_number()
                .over(
                    partition_by=WorkflowExecution.workflow_id,
                    order_by=desc(WorkflowExecution.started),
                )
                .label("row_num"),
            )
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(
                WorkflowExecution.started
                >= datetime.now(tz=timezone.utc) - timedelta(days=7)
            )
            .cte("latest_executions_subquery")
        )

        workflows_with_last_executions_query = (
            select(
                Workflow,
                latest_executions_subquery.c.started,
                latest_executions_subquery.c.execution_time,
                latest_executions_subquery.c.status,
            )
            .outerjoin(
                latest_executions_subquery,
                and_(
                    Workflow.id == latest_executions_subquery.c.workflow_id,
                    latest_executions_subquery.c.row_num <= fetch_last_executions,
                ),
            )
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.is_deleted == False)
            .order_by(Workflow.id, desc(latest_executions_subquery.c.started))
            .limit(15000)
        ).distinct()

        result = session.execute(workflows_with_last_executions_query).all()

    return result
