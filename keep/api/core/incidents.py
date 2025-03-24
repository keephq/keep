import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, case, func, select
from sqlmodel import Session, col, text

from keep.api.core.alerts import get_alert_potential_facet_fields
from keep.api.core.cel_to_sql.properties_mapper import PropertiesMappingException
from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    PropertiesMetadata,
)
from keep.api.core.cel_to_sql.sql_providers.base import CelToSqlException
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider,
)
from keep.api.core.db import engine, enrich_incidents_with_alerts
from keep.api.core.facets import get_facet_options, get_facets
from keep.api.models.db.alert import (
    Alert,
    AlertEnrichment,
    Incident,
    LastAlert,
    LastAlertToIncident,
)
from keep.api.models.db.facet import FacetType
from keep.api.models.facet import FacetDto, FacetOptionDto, FacetOptionsQueryDto
from keep.api.models.incident import IncidentSorting

logger = logging.getLogger(__name__)

incident_field_configurations = [
    FieldMappingConfiguration(
        map_from_pattern="name", map_to=["user_generated_name", "ai_generated_name"]
    ),
    FieldMappingConfiguration(
        map_from_pattern="summary", map_to=["user_summary", "generated_summary"]
    ),
    FieldMappingConfiguration(map_from_pattern="assignee", map_to="assignee"),
    FieldMappingConfiguration(map_from_pattern="severity", map_to="severity"),
    FieldMappingConfiguration(map_from_pattern="status", map_to="status"),
    FieldMappingConfiguration(map_from_pattern="creation_time", map_to="creation_time"),
    FieldMappingConfiguration(map_from_pattern="start_time", map_to="start_time"),
    FieldMappingConfiguration(map_from_pattern="end_time", map_to="end_time"),
    FieldMappingConfiguration(
        map_from_pattern="last_seen_time", map_to="last_seen_time"
    ),
    FieldMappingConfiguration(map_from_pattern="is_predicted", map_to="is_predicted"),
    FieldMappingConfiguration(map_from_pattern="is_candidate", map_to="is_candidate"),
    FieldMappingConfiguration(map_from_pattern="is_visible", map_to="is_visible"),
    FieldMappingConfiguration(map_from_pattern="alerts_count", map_to="alerts_count"),
    FieldMappingConfiguration(map_from_pattern="merged_at", map_to="merged_at"),
    FieldMappingConfiguration(map_from_pattern="merged_by", map_to="merged_by"),
    FieldMappingConfiguration(
        map_from_pattern="hasLinkedIncident", map_to="incident_has_linked_incident"
    ),
    FieldMappingConfiguration(
        map_from_pattern="alert.providerType", map_to="incident_alert_provider_type"
    ),
    FieldMappingConfiguration(
        map_from_pattern="alert.*",
        map_to=["JSON(alert_enrichments).*", "JSON(alert_event).*"],
    ),
]

properties_metadata = PropertiesMetadata(incident_field_configurations)

static_facets = [
    FacetDto(
        id="1e7b1d6e-1c2b-4f8e-9f8e-1c2b4f8e9f8e",
        property_path="status",
        name="Status",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="2e7b1d6e-2c2b-4f8e-9f8e-2c2b4f8e9f8e",
        property_path="severity",
        name="Severity",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="3e7b1d6e-3c2b-4f8e-9f8e-3c2b4f8e9f8e",
        property_path="assignee",
        name="Assignee",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="5e7b1d6e-5c2b-4f8e-9f8e-5c2b4f8e9f8e",
        property_path="alert.providerType",
        name="Source",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="4e7b1d6e-4c2b-4f8e-9f8e-4c2b4f8e9f8e",
        property_path="alert.service",
        name="Service",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="5e247d67-ad9a-4f32-b8d1-8bdf4191d93f",
        property_path="hasLinkedIncident",
        name="Linked incident",
        is_static=True,
        type=FacetType.str,
    ),
]
static_facets_dict = {facet.id: facet for facet in static_facets}


def __build_base_incident_query(tenant_id: str):
    """
    Builds a base query for incidents related to a specific tenant.
    This function constructs a Common Table Expression (CTE) that selects
    incident-related data, including incident ID, alert enrichments, alert event,
    and alert provider type. It joins several tables: LastAlertToIncident, LastAlert,
    Alert, and optionally AlertEnrichment, based on the provided tenant ID.
    Args:
        tenant_id (str): The ID of the tenant for which to build the incident query.
    Returns:
        sqlalchemy.sql.selectable.CTE: A CTE containing the base incident query.
    """
    incidents_alerts_cte = (
        select(
            Incident.id.label("incident_id"),
            AlertEnrichment.enrichments.label("alert_enrichments"),
            Alert.event.label("alert_event"),
            Alert.provider_type.label("incident_alert_provider_type"),
            case(
                (
                    Incident.same_incident_in_the_past_id.isnot(None),
                    True,
                ),
                else_=False,
            ).label("incident_has_linked_incident"),
        )
        .select_from(Incident)
        .outerjoin(
            LastAlertToIncident,
            and_(
                LastAlertToIncident.incident_id == Incident.id,
                LastAlertToIncident.tenant_id == tenant_id,
            ),
        )
        .outerjoin(
            LastAlert,
            and_(
                LastAlert.tenant_id == tenant_id,
                LastAlert.fingerprint == LastAlertToIncident.fingerprint,
            ),
        )
        .outerjoin(
            Alert,
            and_(LastAlert.alert_id == Alert.id, LastAlert.tenant_id == tenant_id),
        )
        .outerjoin(
            AlertEnrichment,
            and_(
                AlertEnrichment.alert_fingerprint == Alert.fingerprint,
                AlertEnrichment.tenant_id == tenant_id,
            ),
        )
    )

    return incidents_alerts_cte


def __build_last_incidents_total_count_query(
    tenant_id: str,
    timeframe: int = None,
    upper_timestamp: datetime = None,
    lower_timestamp: datetime = None,
    is_candidate: bool = False,
    is_predicted: bool = None,
    cel: str = None,
    allowed_incident_ids: Optional[List[str]] = None,
):
    """
    Builds a SQL query to retrieve the last incidents based on various filters and sorting options.

    Args:
        dialect (str): The SQL dialect to use.
        tenant_id (str): The tenant ID to filter incidents.
        limit (int, optional): The maximum number of incidents to return. Defaults to 25.
        offset (int, optional): The number of incidents to skip before starting to return results. Defaults to 0.
        timeframe (int, optional): The number of days to look back from the current date for incidents. Defaults to None.
        upper_timestamp (datetime, optional): The upper bound timestamp for filtering incidents. Defaults to None.
        lower_timestamp (datetime, optional): The lower bound timestamp for filtering incidents. Defaults to None.
        is_candidate (bool, optional): Filter for confirmed incidents. Defaults to False.
        sorting (Optional[IncidentSorting], optional): The sorting criteria for the incidents. Defaults to IncidentSorting.creation_time.
        is_predicted (bool, optional): Filter for predicted incidents. Defaults to None.
        cel (str, optional): The CEL (Common Expression Language) string to convert to SQL. Defaults to None.
        allowed_incident_ids (Optional[List[str]], optional): List of allowed incident IDs to filter. Defaults to None.

    Returns:
        sqlalchemy.sql.selectable.Select: The constructed SQL query.
    """
    incidents_alers_cte = __build_base_incident_query(tenant_id).cte(
        "incidents_alers_cte"
    )
    base_query_cte = (
        select(
            func.count(func.distinct(incidents_alers_cte.c.incident_id)).label(
                "total_count"
            ),
        )
        .select_from(incidents_alers_cte)
        .join(Incident, Incident.id == incidents_alers_cte.c.incident_id)
        .filter(Incident.tenant_id == tenant_id)
        .filter(Incident.is_visible == True)
    )
    query = base_query_cte.filter(Incident.is_candidate == is_candidate)

    if allowed_incident_ids:
        query = query.filter(Incident.id.in_(allowed_incident_ids))

    if is_predicted is not None:
        query = query.filter(Incident.is_predicted == is_predicted)

    if timeframe:
        query = query.filter(
            Incident.start_time
            >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
        )

    if upper_timestamp and lower_timestamp:
        query = query.filter(
            col(Incident.last_seen_time).between(lower_timestamp, upper_timestamp)
        )
    elif upper_timestamp:
        query = query.filter(Incident.last_seen_time <= upper_timestamp)
    elif lower_timestamp:
        query = query.filter(Incident.last_seen_time >= lower_timestamp)

    if cel:
        instance = get_cel_to_sql_provider(properties_metadata)
        sql_filter = instance.convert_to_sql_str(cel)
        query = query.filter(text(sql_filter))

    return query


def __build_last_incidents_query(
    tenant_id: str,
    limit: int = 25,
    offset: int = 0,
    timeframe: int = None,
    upper_timestamp: datetime = None,
    lower_timestamp: datetime = None,
    is_candidate: bool = False,
    sorting: Optional[IncidentSorting] = IncidentSorting.creation_time,
    is_predicted: bool = None,
    cel: str = None,
    allowed_incident_ids: Optional[List[str]] = None,
):
    """
    Builds a SQL query to retrieve the last incidents based on various filters and sorting options.

    Args:
        dialect (str): The SQL dialect to use.
        tenant_id (str): The tenant ID to filter incidents.
        limit (int, optional): The maximum number of incidents to return. Defaults to 25.
        offset (int, optional): The number of incidents to skip before starting to return results. Defaults to 0.
        timeframe (int, optional): The number of days to look back from the current date for incidents. Defaults to None.
        upper_timestamp (datetime, optional): The upper bound timestamp for filtering incidents. Defaults to None.
        lower_timestamp (datetime, optional): The lower bound timestamp for filtering incidents. Defaults to None.
        is_candidate (bool, optional): Filter for confirmed incidents. Defaults to False.
        sorting (Optional[IncidentSorting], optional): The sorting criteria for the incidents. Defaults to IncidentSorting.creation_time.
        is_predicted (bool, optional): Filter for predicted incidents. Defaults to None.
        cel (str, optional): The CEL (Common Expression Language) string to convert to SQL. Defaults to None.
        allowed_incident_ids (Optional[List[str]], optional): List of allowed incident IDs to filter. Defaults to None.

    Returns:
        sqlalchemy.sql.selectable.Select: The constructed SQL query.
    """
    incidents_alers_cte = __build_base_incident_query(tenant_id).cte(
        "incidents_alers_cte"
    )
    base_query_cte = (
        select(
            Incident,
        )
        .select_from(incidents_alers_cte)
        .join(Incident, Incident.id == incidents_alers_cte.c.incident_id)
        .filter(Incident.tenant_id == tenant_id)
        .filter(Incident.is_visible == True)
    )
    query = base_query_cte.filter(Incident.is_candidate == is_candidate)

    if allowed_incident_ids:
        query = query.filter(Incident.id.in_(allowed_incident_ids))

    if is_predicted is not None:
        query = query.filter(Incident.is_predicted == is_predicted)

    if timeframe:
        query = query.filter(
            Incident.start_time
            >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
        )

    if upper_timestamp and lower_timestamp:
        query = query.filter(
            col(Incident.last_seen_time).between(lower_timestamp, upper_timestamp)
        )
    elif upper_timestamp:
        query = query.filter(Incident.last_seen_time <= upper_timestamp)
    elif lower_timestamp:
        query = query.filter(Incident.last_seen_time >= lower_timestamp)

    if sorting:
        query = query.order_by(sorting.get_order_by(Incident), Incident.id)

    if cel:
        instance = get_cel_to_sql_provider(properties_metadata)
        sql_filter = instance.convert_to_sql_str(cel)
        query = query.filter(text(sql_filter))

    distinct_sorting_key = (
        sorting.value[1:] if sorting.value.startswith("-") else sorting.value
    )
    query = query.distinct(text(distinct_sorting_key), Incident.id)

    # Order by start_time in descending order and limit the results
    query = query.limit(limit).offset(offset)
    return query


def get_last_incidents_by_cel(
    tenant_id: str,
    limit: int = 25,
    offset: int = 0,
    timeframe: int = None,
    upper_timestamp: datetime = None,
    lower_timestamp: datetime = None,
    is_candidate: bool = False,
    sorting: Optional[IncidentSorting] = IncidentSorting.creation_time,
    with_alerts: bool = False,
    is_predicted: bool = None,
    cel: str = None,
    allowed_incident_ids: Optional[List[str]] = None,
) -> Tuple[list[Incident], int]:
    """
    Retrieve the last incidents for a given tenant based on various filters and criteria.
    Args:
        tenant_id (str): The ID of the tenant.
        limit (int, optional): The maximum number of incidents to return. Defaults to 25.
        offset (int, optional): The number of incidents to skip before starting to collect the result set. Defaults to 0.
        timeframe (int, optional): The timeframe in which to look for incidents. Defaults to None.
        upper_timestamp (datetime, optional): The upper bound timestamp for filtering incidents. Defaults to None.
        lower_timestamp (datetime, optional): The lower bound timestamp for filtering incidents. Defaults to None.
        is_candidate (bool, optional): Filter for confirmed incidents. Defaults to False.
        sorting (Optional[IncidentSorting], optional): The sorting criteria for the incidents. Defaults to IncidentSorting.creation_time.
        with_alerts (bool, optional): Whether to include alerts in the incidents. Defaults to False.
        is_predicted (bool, optional): Filter for predicted incidents. Defaults to None.
        cel (str, optional): The CEL (Common Event Language) filter. Defaults to None.
        allowed_incident_ids (Optional[List[str]], optional): A list of allowed incident IDs to filter by. Defaults to None.
    Returns:
        Tuple[list[Incident], int]: A tuple containing a list of incidents and the total count of incidents.
    """

    with Session(engine) as session:
        try:
            total_count_query = __build_last_incidents_total_count_query(
                tenant_id=tenant_id,
                timeframe=timeframe,
                upper_timestamp=upper_timestamp,
                lower_timestamp=lower_timestamp,
                is_candidate=is_candidate,
                is_predicted=is_predicted,
                cel=cel,
                allowed_incident_ids=allowed_incident_ids,
            )
            sql_query = __build_last_incidents_query(
                tenant_id=tenant_id,
                limit=limit,
                offset=offset,
                timeframe=timeframe,
                upper_timestamp=upper_timestamp,
                lower_timestamp=lower_timestamp,
                is_candidate=is_candidate,
                sorting=sorting,
                is_predicted=is_predicted,
                cel=cel,
                allowed_incident_ids=allowed_incident_ids,
            )
        except CelToSqlException as e:
            if isinstance(e.__cause__, PropertiesMappingException):
                # if there is an error in mapping properties, return empty list
                logger.error(f"Error mapping properties: {str(e)}")
                return [], 0
            raise e

        total_count = session.exec(total_count_query).one()[0]
        all_records = session.exec(sql_query).all()

        incidents = [row._asdict().get("Incident") for row in all_records]

        if with_alerts:
            enrich_incidents_with_alerts(tenant_id, incidents, session)

    return incidents, total_count


def get_incident_facets_data(
    tenant_id: str,
    allowed_incident_ids: list[str],
    facet_options_query: FacetOptionsQueryDto,
) -> dict[str, list[FacetOptionDto]]:
    """
    Retrieves incident facets data for a given tenant.
    Args:
        tenant_id (str): The ID of the tenant.
        facets_to_load (list[str]): A list of facets to load.
        allowed_incident_ids (list[str]): A list of allowed incident IDs.
        cel (str, optional): A CEL expression to filter the incidents. Defaults to None.
    Returns:
        dict[str, list[FacetOptionDto]]: A dictionary where the keys are facet ids and the values are lists of FacetOptionDto objects.
    """
    if facet_options_query and facet_options_query.facet_queries:
        facets = get_incident_facets(
            tenant_id, facet_options_query.facet_queries.keys()
        )
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
            incidents_alerts_cte.c.incident_has_linked_incident,
            Incident.id.label("entity_id"),
        )
        .select_from(Incident)
        .join(
            incidents_alerts_cte,
            and_(
                Incident.id == incidents_alerts_cte.c.incident_id,
                Incident.tenant_id == tenant_id,
            ),
        )
        .filter(Incident.tenant_id == tenant_id)
    )

    if allowed_incident_ids:
        base_query = base_query.filter(Incident.id.in_(allowed_incident_ids))

    return get_facet_options(
        base_query=base_query,
        facets=facets,
        facet_options_query=facet_options_query,
        properties_metadata=properties_metadata,
    )


def get_incident_facets(
    tenant_id: str, facet_ids_to_load: list[str] = None
) -> list[FacetDto]:
    """
    Retrieve incident facets for a given tenant.

    This function returns a list of facets associated with incidents for a specified tenant.
    If no specific facet IDs are provided, it returns a combination of static facets and
    dynamically loaded facets for the tenant. If specific facet IDs are provided, it returns
    the corresponding facets, loading them dynamically if they are not static.

    Args:
        tenant_id (str): The ID of the tenant for which to retrieve incident facets.
        facet_ids_to_load (list[str], optional): A list of facet IDs to load. If not provided,
            all static facets and dynamically loaded facets for the tenant will be returned.

    Returns:
        list[FacetDto]: A list of FacetDto objects representing the incident facets for the tenant.
    """
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


def get_incident_potential_facet_fields(tenant_id: str) -> list[str]:
    alert_fields = [
        f"alert.{item}" for item in get_alert_potential_facet_fields(tenant_id)
    ]
    incident_fields = [
        item.map_from_pattern
        for item in incident_field_configurations
        if not item.map_from_pattern.startswith("alert.*")
    ]
    seen = set()
    result = []
    for item in incident_fields + alert_fields:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
