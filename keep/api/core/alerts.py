import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy import (
    and_,
    asc,
    desc,
    func,
    select,
)
from sqlmodel import Session, select, text

# This import is required to create the tables
from keep.api.core.facets import get_facet_options, get_facets
from keep.api.models.db.alert import Alert, AlertEnrichment, Incident, LastAlert, LastAlertToIncident
from keep.api.models.db.facet import FacetType
from keep.api.models.facet import FacetDto, FacetOptionDto, FacetOptionsQueryDto
from keep.api.core.db import engine
from keep.api.core.cel_to_sql.properties_metadata import FieldMappingConfiguration, JsonMapping, PropertiesMetadata, SimpleMapping
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import get_cel_to_sql_provider_for_dialect

logger = logging.getLogger(__name__)

alert_field_configurations = [
    FieldMappingConfiguration("source", "filter_provider_type"),
    FieldMappingConfiguration("provider_id", "filter_provider_id"),
    FieldMappingConfiguration(map_from_pattern = "incident.name", map_to=['filter_incident_user_generated_name', 'filter_incident_ai_generated_name']),
    FieldMappingConfiguration(map_from_pattern = "*", map_to=["filter_alert_enrichment_json", "filter_alert_event_json"], is_json=True),
]
properties_metadata = PropertiesMetadata(alert_field_configurations)


static_facets = [
    FacetDto(
        id="f8a91ac7-4916-4ad0-9b46-a5ddb85bfbb8",
        property_path="severity",
        name="Severity",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="5dd1519c-6277-4109-ad95-c19d2f4f15e3",
        property_path="status",
        name="Status",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="461bef05-fc20-4363-b427-9d26fe064e7f",
        property_path="source",
        name="Source",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="6afa12d7-21df-4694-8566-fd56d5ee2266",
        property_path="incident.name",
        name="Incident",
        is_static=True,
        type=FacetType.str
    )
]
static_facets_dict = {facet.id: facet for facet in static_facets}

def __build_query_for_filtering(tenant_id: str):
    return (
        select(
            LastAlert.alert_id,
            AlertEnrichment.id.label("alert_enrichment_id"),
            AlertEnrichment.tenant_id.label("alert_enrichment_tenant_id"),
            AlertEnrichment.alert_fingerprint.label("alert_enrichment_fingerprint"),
            LastAlert.tenant_id.label("last_alert_tenant_id"),
            LastAlert.first_timestamp.label("startedAt"),
            LastAlert.alert_id.label("entity_id"),
            AlertEnrichment.enrichments.label('filter_alert_enrichment_json'),
            Incident.user_generated_name.label("filter_incident_user_generated_name"),
            Incident.ai_generated_name.label("filter_incident_ai_generated_name"),
            Alert.event.label("filter_alert_event_json"),
            Alert.provider_type.label("filter_provider_type"),
            Alert.provider_id.label("filter_provider_id"),
        )
        .select_from(LastAlert)
        .join(Alert, and_(Alert.id == LastAlert.alert_id, Alert.tenant_id == LastAlert.tenant_id))
        .outerjoin(
            AlertEnrichment,
            and_(
                LastAlert.tenant_id == AlertEnrichment.tenant_id,
                LastAlert.fingerprint == AlertEnrichment.alert_fingerprint,
            ),
        )
        .outerjoin(
            LastAlertToIncident,
            and_(
                LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                LastAlert.fingerprint == LastAlertToIncident.fingerprint,
            ),
        )
        .outerjoin(
            Incident,
            and_(
                LastAlertToIncident.tenant_id == Incident.tenant_id,
                LastAlertToIncident.incident_id == Incident.id,
            ),
        )
        .where(LastAlert.tenant_id == tenant_id)
    )

def build_alerts_query(
        dialect_name: str,
        tenant_id,
        provider_id=None,
        timeframe=None,
        upper_timestamp=None,
        lower_timestamp=None,
        fingerprints=None,
        cel=None,
        sort_by=None,
        sort_dir=None
    ):
    base = __build_query_for_filtering(tenant_id)
    query = (
        select(
            Alert,
            AlertEnrichment,
            # AlertEnrichment.id.label('alert_enrichment_id'),
            # AlertEnrichment.tenant_id.label('alert_enrichment_tenant_id'),
            # AlertEnrichment.alert_fingerprint.label('alert_enrichment_fingerprint'),
            # AlertEnrichment.enrichments.label('alert_enrichment_json'),
            base.c.startedAt,
        )
        .select_from(base)
        .join(
            Alert,
            and_(
                base.c.last_alert_tenant_id == Alert.tenant_id, base.c.alert_id == Alert.id
            ),
        )
        .outerjoin(AlertEnrichment, and_(AlertEnrichment.tenant_id == Alert.tenant_id, AlertEnrichment.alert_fingerprint == Alert.fingerprint))
    )

    if timeframe:
        query = query.where(
            LastAlert.timestamp
            >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
        )

    # Apply additional filters
    filter_conditions = []

    if upper_timestamp is not None:
        filter_conditions.append(LastAlert.timestamp < upper_timestamp)

    if lower_timestamp is not None:
        filter_conditions.append(LastAlert.timestamp >= lower_timestamp)

    if fingerprints:
        filter_conditions.append(LastAlert.fingerprint.in_(tuple(fingerprints)))

    logger.info(f"filter_conditions: {filter_conditions}")

    if filter_conditions:
        query = query.where(*filter_conditions)

    if provider_id:
        query = query.where(Alert.provider_id == provider_id)

    if cel:
        cel_to_sql_provider_type = get_cel_to_sql_provider_for_dialect(dialect_name)
        instance = cel_to_sql_provider_type(properties_metadata)
        sql_filter = instance.convert_to_sql_str(cel)
        query = query.where(text(sql_filter))

    if sort_by:
        provider_type = get_cel_to_sql_provider_for_dialect(dialect=dialect_name)
        instance = provider_type(properties_metadata)
        metadata = properties_metadata.get_property_metadata(sort_by)
        group_by_exp = []

        for item in metadata:
            if isinstance(item, JsonMapping):
                group_by_exp.append(
                    instance.json_extract_as_text(item.json_prop, item.prop_in_json)
                )
            elif isinstance(metadata[0], SimpleMapping):
                group_by_exp.append(item.map_to)
        
        casted = f"{instance.coalesce([instance.cast(item, str) for item in group_by_exp])}"

        if sort_dir == "desc":
            query = query.order_by(desc(text(casted)))
        else:
            query = query.order_by(asc(text(casted)))

    return query

def get_last_alerts(
    tenant_id,
    provider_id=None,
    limit=1000,
    offset=0,
    timeframe=None,
    upper_timestamp=None,
    lower_timestamp=None,
    with_incidents=False,
    fingerprints=None,
    cel=None,
    sort_by=None,
    sort_dir=None
) -> Tuple[list[Alert], int]:
    with Session(engine) as session:
        dialect_name = session.bind.dialect.name

        query = build_alerts_query(
            dialect_name,
            tenant_id,
            provider_id,
            timeframe,
            upper_timestamp,
            lower_timestamp,
            fingerprints,
            cel,
            sort_by,
            sort_dir
        )

        query = query.group_by(Alert.id,AlertEnrichment.id)

        # Execute the query
        start_time = datetime.now()
        total_count = session.exec(select(func.count()).select_from(query)).one()
        alerts_with_start = session.execute(
            query.order_by(desc(Alert.timestamp)).limit(limit).offset(offset)
        ).all()
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        logger.info(f"Query execution time: {execution_time} seconds")

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
    base_query = select(base_query_cte)

    return get_facet_options(
        base_query=base_query,
        facets=facets,
        facet_options_query=facet_options_query,
        properties_metadata=properties_metadata,
    )

def get_alert_facets(tenant_id: str, facet_ids_to_load: list[str] = None) -> list[FacetDto]:
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
