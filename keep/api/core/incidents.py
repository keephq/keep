from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlmodel import Session, col, text

from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata, FieldMappingConfiguration
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider_for_dialect,
)

from keep.api.core.facets import get_facet_options, get_facets
from keep.api.models.alert import (
    IncidentSorting,
)

from keep.api.core.db import engine, enrich_incidents_with_alerts
from keep.api.models.db.alert import (
    Alert,
    AlertEnrichment,
    Incident,
    LastAlert,
    LastAlertToIncident,
)
from keep.api.models.db.facet import FacetType
from keep.api.models.facet import FacetDto, FacetOptionDto


incident_field_configurations = [
    FieldMappingConfiguration("user_generated_name", "user_generated_name"),
    FieldMappingConfiguration("ai_generated_name", "ai_generated_name"),
    FieldMappingConfiguration("user_summary", "user_summary"),
    FieldMappingConfiguration("generated_summary", "generated_summary"),
    FieldMappingConfiguration("assignee", "assignee"),
    FieldMappingConfiguration("severity", "severity"),
    FieldMappingConfiguration("status", "status"),
    FieldMappingConfiguration("creation_time", "creation_time"),
    FieldMappingConfiguration("start_time", "start_time"),
    FieldMappingConfiguration("end_time", "end_time"),
    FieldMappingConfiguration("last_seen_time", "last_seen_time"),
    FieldMappingConfiguration("is_predicted", "is_predicted"),
    FieldMappingConfiguration("is_confirmed", "is_confirmed"),
    FieldMappingConfiguration("alerts_count", "alerts_count"),
    FieldMappingConfiguration("affected_services", "affected_services"),
    FieldMappingConfiguration("sources", "sources"),
    FieldMappingConfiguration("rule_id", "rule_id"),
    FieldMappingConfiguration("rule_fingerprint", "rule_fingerprint"),
    FieldMappingConfiguration("fingerprint", "fingerprint"),
    FieldMappingConfiguration("same_incident_in_the_past_id", "incident_same_incident_in_the_past_id"),
    FieldMappingConfiguration("merged_into_incident_id", "merged_into_incident_id"),
    FieldMappingConfiguration("merged_at", "merged_at"),
    FieldMappingConfiguration("merged_by", "merged_by"),
    FieldMappingConfiguration("alert.provider_type", "incident_alert_provider_type"),
    FieldMappingConfiguration(map_from_pattern = "alert.*", map_to=["alert_enrichments", "alert_event"], is_json=True),
]

properties_metadata = PropertiesMetadata(incident_field_configurations)

static_facets = [
    FacetDto(
        id="1e7b1d6e-1c2b-4f8e-9f8e-1c2b4f8e9f8e",
        property_path="status",
        name="Status",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="2e7b1d6e-2c2b-4f8e-9f8e-2c2b4f8e9f8e",
        property_path="severity",
        name="Severity",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="3e7b1d6e-3c2b-4f8e-9f8e-3c2b4f8e9f8e",
        property_path="assignee",
        name="Assignee",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="4e7b1d6e-4c2b-4f8e-9f8e-4c2b4f8e9f8e",
        property_path="alert.service",
        name="Service",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="5e7b1d6e-5c2b-4f8e-9f8e-5c2b4f8e9f8e",
        property_path="alert.provider_type",
        name="Source",
        is_static=True,
        type=FacetType.str
    )
]
static_facets_dict = {facet.id: facet for facet in static_facets}

def __build_base_incident_query(tenant_id: str):
    incidents_alerts_cte = (
        select(
            LastAlertToIncident.incident_id.label("incident_id"),
            AlertEnrichment.enrichments.label("alert_enrichments"),
            Alert.event.label("alert_event"),
            Alert.provider_type.label("incident_alert_provider_type")
        )
        .select_from(LastAlertToIncident)
        .join(
            LastAlert,
            and_(
                LastAlert.tenant_id == tenant_id,
                LastAlert.fingerprint == LastAlertToIncident.fingerprint
            )
        )
        .join(
            Alert,
            and_(
                LastAlert.alert_id == Alert.id,
                LastAlert.tenant_id == tenant_id
            )
        )
        .outerjoin(
            AlertEnrichment,
            and_(
                AlertEnrichment.alert_fingerprint == Alert.fingerprint,
                AlertEnrichment.tenant_id == tenant_id
            )
        )
    )
    
    return incidents_alerts_cte


def __build_last_incidents_query(
    dialect: str,
    tenant_id: str,
    limit: int = 25,
    offset: int = 0,
    timeframe: int = None,
    upper_timestamp: datetime = None,
    lower_timestamp: datetime = None,
    is_confirmed: bool = False,
    sorting: Optional[IncidentSorting] = IncidentSorting.creation_time,
    is_predicted: bool = None,
    cel: str = None,
    allowed_incident_ids: Optional[List[str]] = None,
):
    provider_type = get_cel_to_sql_provider_for_dialect(dialect)
    instance = provider_type(properties_metadata)
    query_metadata = instance.convert_to_sql_str(cel)
    incidents_alers_cte = __build_base_incident_query(tenant_id).cte("incidents_alers_cte")
    base_query_cte = (
            select(
                Incident
            )
            .select_from(Incident)
            .outerjoin(incidents_alers_cte, Incident.id == incidents_alers_cte.c.incident_id)
            .filter(Incident.tenant_id == tenant_id)
        )
    query_cte = base_query_cte.filter(Incident.is_confirmed == is_confirmed)

    if allowed_incident_ids:
        query_cte = query_cte.filter(Incident.id.in_(allowed_incident_ids))

    if is_predicted is not None:
        query_cte = query_cte.filter(Incident.is_predicted == is_predicted)

    if timeframe:
        query_cte = query_cte.filter(
            Incident.start_time
            >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
        )

    if upper_timestamp and lower_timestamp:
        query_cte = query_cte.filter(
            col(Incident.last_seen_time).between(lower_timestamp, upper_timestamp)
        )
    elif upper_timestamp:
        query_cte = query_cte.filter(Incident.last_seen_time <= upper_timestamp)
    elif lower_timestamp:
        query_cte = query_cte.filter(Incident.last_seen_time >= lower_timestamp)

    if sorting:
        query_cte = query_cte.order_by(sorting.get_order_by(Incident))

    query_cte = query_cte.filter(text(query_metadata.where)).group_by(Incident.id)

    # Order by start_time in descending order and limit the results
    query_cte = query_cte.limit(limit).offset(offset)

    return query_cte


def get_last_incidents_by_cel(
    tenant_id: str,
    limit: int = 25,
    offset: int = 0,
    timeframe: int = None,
    upper_timestamp: datetime = None,
    lower_timestamp: datetime = None,
    is_confirmed: bool = False,
    sorting: Optional[IncidentSorting] = IncidentSorting.creation_time,
    with_alerts: bool = False,
    is_predicted: bool = None,
    cel: str = None,
    allowed_incident_ids: Optional[List[str]] = None,
) -> Tuple[list[Incident], int]:
    """
    Get the last incidents and total amount of incidents.

    Args:
        tenant_id (str): The tenant_id to filter the incidents by.
        limit (int): Amount of objects to return
        offset (int): Current offset for
        timeframe (int|null): Return incidents only for the last <N> days
        is_confirmed (bool): Return confirmed incidents or predictions
        upper_timestamp: datetime = None,
        lower_timestamp: datetime = None,
        is_confirmed (bool): filter incident candidates or real incidents
        sorting: Optional[IncidentSorting]: how to sort the data
        with_alerts (bool): Pre-load alerts or not
        is_predicted (bool): filter only incidents predicted by KeepAI
        filters (dict): dict of filters
    Returns:
        List[Incident]: A list of Incident objects.
    """
    with Session(engine) as session:
        sql_query = __build_last_incidents_query(
            dialect=session.bind.dialect.name,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            timeframe=timeframe,
            upper_timestamp=upper_timestamp,
            lower_timestamp=lower_timestamp,
            is_confirmed=is_confirmed,
            sorting=sorting,
            is_predicted=is_predicted,
            cel=cel,
            allowed_incident_ids=allowed_incident_ids,
        )

        total_count = session.exec(select(func.count()).select_from(sql_query)).scalar()
        all_records = session.exec(sql_query).all()
        incidents = [row._asdict().get('Incident') for row in all_records]

        if with_alerts:
            enrich_incidents_with_alerts(tenant_id, incidents, session)

    return incidents, total_count


def get_incident_facets_data(
    tenant_id: str,
    facets_to_load: list[str],
    allowed_incident_ids: list[str],
    cel: str = None,
) -> dict[str, list[FacetOptionDto]]:
    if facets_to_load:
        facets = get_incident_facets(tenant_id, facets_to_load)
    else:
        facets = static_facets

    incidents_alerts_cte = __build_base_incident_query(tenant_id).cte(
        "incidents_alerts_cte"
    )
    base_query = (
        select(
            Incident,
            incidents_alerts_cte.c.alert_enrichments,
            incidents_alerts_cte.c.alert_event,
            incidents_alerts_cte.c.incident_alert_provider_type,
            Incident.id.label("entity_id"),
        )
        .select_from(Incident)
        .outerjoin(
            incidents_alerts_cte, Incident.id == incidents_alerts_cte.c.incident_id
        )
        .filter(Incident.tenant_id == tenant_id)
    )

    if allowed_incident_ids:
        base_query = base_query.filter(Incident.id.in_(allowed_incident_ids))

    return get_facet_options(
        base_query=base_query,
        cel=cel,
        facets=facets,
        properties_metadata=properties_metadata,
    )


def get_incident_facets(tenant_id: str, facet_ids_to_load: list[str] = None) -> list[FacetDto]:
    not_static_facet_ids = []
    facets = []

    if not facet_ids_to_load:
        return static_facets + get_facets(tenant_id, "incident")

    if facet_ids_to_load:
        for facet_id in facet_ids_to_load:
            if facet_id not in static_facets_dict:
                not_static_facet_ids.append(facet_id)
                continue

            facets.append(static_facets_dict[facet_id])

    if not_static_facet_ids:
        facets += get_facets(tenant_id, "incident", not_static_facet_ids)

    return facets
