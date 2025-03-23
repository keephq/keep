import datetime
import logging
import os
from typing import Tuple

from sqlalchemy import and_, asc, desc, func, literal_column, select
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, text

from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    JsonFieldMapping,
    PropertiesMetadata,
    SimpleFieldMapping,
    remap_fields_configurations,
)
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider,
)
from keep.api.core.db import engine

# This import is required to create the tables
from keep.api.core.facets import get_facet_options, get_facets
from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.api.models.db.alert import (
    Alert,
    AlertEnrichment,
    AlertField,
    Incident,
    LastAlert,
    LastAlertToIncident,
)
from keep.api.models.db.facet import FacetType
from keep.api.models.db.incident import IncidentStatus
from keep.api.models.facet import FacetDto, FacetOptionDto, FacetOptionsQueryDto

logger = logging.getLogger(__name__)

alerts_hard_limit = int(os.environ.get("KEEP_LAST_ALERTS_LIMIT", 50000))

alert_field_configurations = [
    FieldMappingConfiguration(
        map_from_pattern="source", map_to="filter_provider_type", data_type=str
    ),
    FieldMappingConfiguration(
        map_from_pattern="providerId", map_to="filter_provider_id", data_type=str
    ),
    FieldMappingConfiguration(
        map_from_pattern="providerType", map_to="filter_provider_type", data_type=str
    ),
    FieldMappingConfiguration(
        map_from_pattern="timestamp",
        map_to="filter_timestamp",
        data_type=datetime.datetime,
    ),
    FieldMappingConfiguration(
        map_from_pattern="fingerprint", map_to="filter_fingerprint", data_type=str
    ),
    FieldMappingConfiguration(
        map_from_pattern="startedAt", map_to="startedAt", data_type=datetime.datetime
    ),
    FieldMappingConfiguration(
        map_from_pattern="incident.id",
        map_to=[
            "filter_incident_id",
        ],
        data_type=str,
    ),
    FieldMappingConfiguration(
        map_from_pattern="incident.name",
        map_to=[
            "filter_incident_user_generated_name",
            "filter_incident_ai_generated_name",
        ],
        data_type=str,
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
        data_type=str,
    ),
    FieldMappingConfiguration(
        map_from_pattern="lastReceived",
        map_to=[
            "JSON(filter_alert_enrichment_json).*",
            "JSON(filter_alert_event_json).*",
        ],
        data_type=datetime.datetime,
    ),
    FieldMappingConfiguration(
        map_from_pattern="status",
        map_to=[
            "JSON(filter_alert_enrichment_json).*",
            "JSON(filter_alert_event_json).*",
        ],
        enum_values=list(reversed([item.value for _, item in enumerate(AlertStatus)])),
        data_type=str,
    ),
    FieldMappingConfiguration(
        map_from_pattern="firingCounter",
        map_to=[
            "JSON(filter_alert_enrichment_json).*",
            "JSON(filter_alert_event_json).*",
        ],
        data_type=int,
    ),
    FieldMappingConfiguration(
        map_from_pattern="*",
        map_to=[
            "JSON(filter_alert_enrichment_json).*",
            "JSON(filter_alert_event_json).*",
        ],
        data_type=str,
    ),
]
alias_column_mapping = {
    "filter_timestamp": "lastalert.timestamp",
    "filter_provider_id": "alert.provider_id",
    "filter_provider_type": "alert.provider_type",
    "filter_incident_id": "incident.id",
    "filter_incident_user_generated_name": "incident.user_generated_name",
    "filter_incident_ai_generated_name": "incident.ai_generated_name",
    "filter_alert_enrichment_json": "alertenrichment.enrichments",
    "filter_alert_event_json": "alert.event",
    "filter_fingerprint": "lastalert.fingerprint",
}

remapped_field_configurations = remap_fields_configurations(
    alias_column_mapping, alert_field_configurations
)

properties_metadata = PropertiesMetadata(alert_field_configurations)
remapped_properties_metadata = PropertiesMetadata(remapped_field_configurations)

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


def get_threeshold_query(tenant_id: str):
    return func.coalesce(
        select(LastAlert.timestamp)
        .select_from(LastAlert)
        .where(LastAlert.tenant_id == tenant_id)
        .order_by(LastAlert.timestamp.desc())
        .limit(1)
        .offset(alerts_hard_limit - 1),
        datetime.datetime.min,
    )


def __build_query_for_filtering(tenant_id: str):
    select_args = [
        LastAlert.alert_id,
        LastAlert.tenant_id.label("last_alert_tenant_id"),
        LastAlert.first_timestamp.label("startedAt"),
        LastAlert.alert_id.label("entity_id"),
        LastAlert.fingerprint.label("alert_fingerprint"),
    ]

    for key, value in alias_column_mapping.items():
        select_args.append(literal_column(value).label(key))

    query = select(*select_args).select_from(LastAlert)

    query = query.join(
        Alert,
        and_(Alert.id == LastAlert.alert_id, Alert.tenant_id == LastAlert.tenant_id),
    ).outerjoin(
        AlertEnrichment,
        and_(
            LastAlert.tenant_id == AlertEnrichment.tenant_id,
            LastAlert.fingerprint == AlertEnrichment.alert_fingerprint,
        ),
    )

    query = query.outerjoin(
        LastAlertToIncident,
        and_(
            LastAlert.tenant_id == LastAlertToIncident.tenant_id,
            LastAlert.fingerprint == LastAlertToIncident.fingerprint,
        ),
    ).outerjoin(
        Incident,
        and_(
            LastAlertToIncident.tenant_id == Incident.tenant_id,
            LastAlertToIncident.incident_id == Incident.id,
            Incident.status == IncidentStatus.FIRING.value,
        ),
    )

    query = query.filter(LastAlert.tenant_id == tenant_id)
    query = query.filter(LastAlert.timestamp >= get_threeshold_query(tenant_id))
    return query


def __build_query_for_filtering_v2(
    tenant_id: str, select_args: list, cel=None, limit=None, fetch_alerts_data=True
):
    fetch_incidents = cel and "incident." in cel
    cel_to_sql_instance = get_cel_to_sql_provider(remapped_properties_metadata)
    sql_filter = None
    involved_fields = []

    if cel:
        cel_to_sql_result = cel_to_sql_instance.convert_to_sql_str_v2(cel)
        sql_filter = cel_to_sql_result.sql
        involved_fields = cel_to_sql_result.involved_fields
        fetch_incidents = next(
            (
                True
                for field in involved_fields
                if field.field_name.startswith("incident.")
            ),
            False,
        )

    query = select(*select_args).select_from(LastAlert)

    if fetch_alerts_data:
        query = query.join(
            Alert,
            and_(
                Alert.id == LastAlert.alert_id, Alert.tenant_id == LastAlert.tenant_id
            ),
        ).outerjoin(
            AlertEnrichment,
            and_(
                LastAlert.tenant_id == AlertEnrichment.tenant_id,
                LastAlert.fingerprint == AlertEnrichment.alert_fingerprint,
            ),
        )

    if fetch_incidents:
        query = query.outerjoin(
            LastAlertToIncident,
            and_(
                LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                LastAlert.fingerprint == LastAlertToIncident.fingerprint,
            ),
        ).outerjoin(
            Incident,
            and_(
                LastAlertToIncident.tenant_id == Incident.tenant_id,
                LastAlertToIncident.incident_id == Incident.id,
                Incident.status == IncidentStatus.FIRING.value,
            ),
        )

    query = query.filter(LastAlert.tenant_id == tenant_id)
    query = query.filter(LastAlert.timestamp >= get_threeshold_query(tenant_id))
    involved_fields = []

    if sql_filter:
        query = query.where(text(sql_filter))
    return {
        "query": query,
        "involved_fields": involved_fields,
        "fetch_incidents": fetch_incidents,
    }

def build_total_alerts_query(tenant_id, cel=None, limit=None):
    fetch_incidents = cel and "incident." in cel
    fetch_alerts_data = cel is not None or cel != ""

    count_funct = (
        func.count(func.distinct(LastAlert.alert_id))
        if fetch_incidents
        else func.count(1)
    )
    built_query_result = __build_query_for_filtering_v2(
        tenant_id=tenant_id,
        cel=cel,
        select_args=[count_funct],
        limit=limit,
        fetch_alerts_data=fetch_alerts_data,
    )

    return built_query_result["query"]


def build_alerts_query(
    tenant_id,
    cel=None,
    sort_by=None,
    sort_dir=None,
    limit=None,
    offset=None,
):
    cel_to_sql_instance = get_cel_to_sql_provider(remapped_properties_metadata)

    if not sort_by:
        sort_by = "timestamp"
        sort_dir = "desc"

    sort_by_exp = cel_to_sql_instance.get_order_by_exp(sort_by)

    built_query_result = __build_query_for_filtering_v2(
        tenant_id,
        select_args=[
            Alert,
            AlertEnrichment,
            LastAlert.first_timestamp.label("startedAt"),
            literal_column(sort_by_exp),
        ],
        cel=cel,
    )
    query = built_query_result["query"]
    fetch_incidents = built_query_result["fetch_incidents"]

    if fetch_incidents:
        if sort_dir == "desc":
            query = query.order_by(desc(text(sort_by_exp)), Alert.id)
        else:
            query = query.order_by(asc(text(sort_by_exp)), Alert.id)

        query = query.distinct(text(sort_by_exp), Alert.id)
    else:
        if sort_dir == "desc":
            query = query.order_by(desc(text(sort_by_exp)))
        else:
            query = query.order_by(asc(text(sort_by_exp)))

    if limit is not None:
        query = query.limit(limit)

    if offset is not None:
        query = query.offset(offset)

    return query


def query_last_alerts(
    tenant_id, limit=1000, offset=0, cel=None, sort_by=None, sort_dir=None
) -> Tuple[list[Alert], int]:
    if limit is None:
        limit = 1000
    if offset is None:
        offset = 0

    with Session(engine) as session:
        # Shahar: this happens when the frontend query builder fails to build a query
        if cel == "1 == 1":
            logger.warning("Failed to build query for alerts")
            cel = ""
        try:
            total_count_query = build_total_alerts_query(
                tenant_id=tenant_id, cel=cel, limit=alerts_hard_limit
            )
            total_count = session.exec(total_count_query).one()[0]

            if not limit:
                return [], total_count

            if offset >= alerts_hard_limit:
                return [], total_count

            if offset + limit > alerts_hard_limit:
                limit = alerts_hard_limit - offset

            data_query = build_alerts_query(
                tenant_id, cel, sort_by, sort_dir, limit, offset
            )
            strq = str(
                data_query.compile(
                    compile_kwargs={"literal_binds": True}, dialect=session.bind.dialect
                )
            )
            alerts_with_start = session.execute(data_query).all()
        except OperationalError as e:
            logger.warning(f"Failed to query alerts for CEL '{cel}': {e}")
            return [], 0

        # Process results based on dialect
        alerts = []
        for alert_data in alerts_with_start:
            alert: Alert = alert_data[0]
            alert.alert_enrichment = alert_data[1]
            alert.event["startedAt"] = str(alert_data[2])
            alert.event["event_id"] = str(alert.id)
            alerts.append(alert)

        return alerts, total_count


def get_alert_facets_data(
    tenant_id: str,
    facet_options_query: FacetOptionsQueryDto,
) -> dict[str, list[FacetOptionDto]]:
    if facet_options_query and facet_options_query.facet_queries:
        facets = get_alert_facets(tenant_id, facet_options_query.facet_queries.keys())
    else:
        facets = static_facets

    base_query_cte = __build_query_for_filtering(tenant_id).cte("alerts_query")

    return get_facet_options(
        base_query=base_query_cte,
        facets=facets,
        facet_options_query=facet_options_query,
        properties_metadata=properties_metadata,
    )


def get_alert_facets(
    tenant_id: str, facet_ids_to_load: list[str] = None
) -> list[FacetDto]:
    not_static_facet_ids = []
    facets = []

    if not facet_ids_to_load:
        return static_facets + get_facets(tenant_id, "alert")

    if facet_ids_to_load:
        for facet_id in facet_ids_to_load:
            if facet_id not in static_facets_dict:
                not_static_facet_ids.append(facet_id)
                continue

            facets.append(static_facets_dict[facet_id])

    if not_static_facet_ids:
        facets += get_facets(tenant_id, "alert", not_static_facet_ids)

    return facets


def get_alert_potential_facet_fields(tenant_id: str) -> list[str]:
    with Session(engine) as session:
        query = (
            select(AlertField.field_name)
            .select_from(AlertField)
            .where(AlertField.tenant_id == tenant_id)
            .distinct(AlertField.field_name)
        )
        result = session.exec(query).all()
        return [row[0] for row in result]
