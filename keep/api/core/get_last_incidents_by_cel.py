"""
Keep main database module.

This module contains the CRUD database functions for Keep.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple
from uuid import UUID, uuid4

# from pydantic import BaseModel
from pydantic import BaseModel
from sqlalchemy import Select, and_, func, literal, literal_column, select
from sqlmodel import Session, text

from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider_for_dialect,
)

# This import is required to create the tables
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
from keep.api.models.db.facet import Facet, FacetType

# from keep.api.models.db.facet import Facet, FacetEntityType


known_fields = {
    "provider_type": {  # redirects provider_type from cel to alert.provider_type in SQL
        "type": "string",
        "field": "incident_alert_provider_type",
        "mapping_type": "one_to_one",
    },
    "user_generated_name": {
        "type": "string",
        "field": "user_generated_name",
        "mapping_type": "one_to_one",
    },
    "ai_generated_name": {
        "type": "string",
        "field": "ai_generated_name",
        "mapping_type": "one_to_one",
    },
    "user_summary": {
        "type": "string",
        "field": "user_summary",
        "mapping_type": "one_to_one",
    },
    "generated_summary": {
        "type": "string",
        "field": "generated_summary",
        "mapping_type": "one_to_one",
    },
    "assignee": {"type": "string", "field": "assignee", "mapping_type": "one_to_one"},
    "severity": {"type": "string", "field": "severity", "mapping_type": "one_to_one"},
    "status": {"type": "string", "field": "status", "mapping_type": "one_to_one"},
    "creation_time": {
        "type": "datetime",
        "field": "creation_time",
        "mapping_type": "one_to_one",
    },
    "start_time": {
        "type": "datetime",
        "field": "start_time",
        "mapping_type": "one_to_one",
    },
    "end_time": {"type": "datetime", "field": "end_time", "mapping_type": "one_to_one"},
    "last_seen_time": {
        "type": "datetime",
        "field": "last_seen_time",
        "mapping_type": "one_to_one",
    },
    "is_predicted": {
        "type": "boolean",
        "field": "is_predicted",
        "mapping_type": "one_to_one",
    },
    "is_confirmed": {
        "type": "boolean",
        "field": "is_confirmed",
        "mapping_type": "one_to_one",
    },
    "alerts_count": {
        "type": "integer",
        "field": "alerts_count",
        "mapping_type": "one_to_one",
    },
    "affected_services": {
        "type": "json",
        "field": "services",
        "mapping_type": "one_to_one",
    },
    "sources": {"type": "json", "field": "alert_sources", "mapping_type": "one_to_one"},
    "rule_id": {"type": "string", "field": "rule_id", "mapping_type": "one_to_one"},
    "rule_fingerprint": {
        "type": "string",
        "field": "rule_fingerprint",
        "mapping_type": "one_to_one",
    },
    "fingerprint": {
        "type": "string",
        "field": "fingerprint",
        "mapping_type": "one_to_one",
    },
    "same_incident_in_the_past_id": {
        "type": "string",
        "field": "incident_same_incident_in_the_past_id",
        "mapping_type": "one_to_one",
    },
    "merged_into_incident_id": {
        "type": "string",
        "field": "merged_into_incident_id",
        "mapping_type": "one_to_one",
    },
    "merged_at": {
        "type": "datetime",
        "field": "merged_at",
        "mapping_type": "one_to_one",
    },
    "merged_by": {"type": "string", "field": "merged_by", "mapping_type": "one_to_one"},
    "*": {  # redirects all other fields from cel to merged_json(event + enrichments) in SQL
        "type": "json",
        "take_from": ["incident_alerts.event", "incident_alerts.enrichments"],
    },
}

incidents_alerts_cte = """
                    WITH incident_alerts AS (
                        SELECT 
                            lastalerttoincident.incident_id as incident_id,
                            alertenrichment.enrichments AS enrichments,
                            alert.event AS event,
                            alert.provider_type AS incident_alert_provider_type
                        FROM 
                            lastalerttoincident
                        INNER JOIN 
                            lastalert 
                            ON lastalert.tenant_id = lastalerttoincident.tenant_id 
                            AND lastalert.fingerprint = lastalerttoincident.fingerprint
                        INNER JOIN 
                            alert 
                            ON lastalert.alert_id = alert.id
                        LEFT OUTER JOIN alertenrichment 
                            ON alert.fingerprint = alertenrichment.alert_fingerprint
                        LEFT OUTER JOIN 
                            alertenrichment AS alertenrichment_1 
                            ON alert.fingerprint = alertenrichment_1.alert_fingerprint 
                            AND alert.tenant_id = lastalerttoincident.tenant_id
                    )"""


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
) -> str:
    instance = get_cel_to_sql_provider_for_dialect(
        dialect, known_fields_mapping=known_fields
    )
    query_metadata = instance.convert_to_sql_str(cel)

    where_filter = (
        f"incident.tenant_id = '{tenant_id}' AND incident.is_confirmed = {is_confirmed}"
    )

    if allowed_incident_ids:
        where_filter += f' AND incident.id IN {", ".join(allowed_incident_ids)}'

    if is_predicted is not None:
        where_filter += f" AND incident.is_predicted = {is_predicted}"

    if timeframe:
        where_filter += f" AND incident.start_time >= {datetime.now(tz=timezone.utc) - timedelta(days=timeframe)}"

    if upper_timestamp and lower_timestamp:
        where_filter += f" AND (incident.last_seen_time BETWEEN {lower_timestamp} AND {upper_timestamp})"
    elif upper_timestamp:
        where_filter += f" AND incident.last_seen_time <= {upper_timestamp}"
    elif lower_timestamp:
        where_filter += f" AND incident.last_seen_time >= {lower_timestamp}"

    if query_metadata.where:
        where_filter += f" AND ({query_metadata.where})"

    sql_cte = f"""
            {incidents_alerts_cte},

            all_incidents AS (
                SELECT
                    incident.id AS id, 
                    incident.tenant_id AS tenant_id, 
                    incident.user_generated_name AS user_generated_name, 
                    incident.ai_generated_name AS ai_generated_name, 
                    incident.user_summary AS user_summary, 
                    incident.generated_summary AS generated_summary, 
                    incident.assignee AS assignee, 
                    incident.severity AS severity, 
                    incident.status AS status, 
                    incident.creation_time AS creation_time, 
                    incident.start_time AS start_time, 
                    incident.end_time AS end_time, 
                    incident.last_seen_time AS last_seen_time, 
                    incident.is_predicted AS is_predicted, 
                    incident.is_confirmed AS is_confirmed, 
                    incident.alerts_count AS alerts_count, 
                    incident.affected_services AS services, 
                    incident.sources AS alert_sources, 
                    incident.rule_id AS rule_id, 
                    incident.rule_fingerprint AS rule_fingerprint, 
                    incident.fingerprint AS fingerprint, 
                    incident.same_incident_in_the_past_id AS incident_same_incident_in_the_past_id, 
                    incident.merged_into_incident_id AS merged_into_incident_id, 
                    incident.merged_at AS merged_at, 
                    incident.merged_by AS merged_by
                FROM 
                    incident
                LEFT JOIN incident_alerts 
                    ON incident.id = incident_alerts.incident_id
                {f'WHERE {where_filter}' if where_filter else ''}
                GROUP BY 
                    incident.id
            )
        """

    select_query = sql_cte + " SELECT * FROM all_incidents"
    count_query = sql_cte + " SELECT COUNT(1) FROM all_incidents"

    if sorting:
        field = sorting.value
        sort_dir = "ASC"

        if field.startswith("-"):
            field = field[1:]
            sort_dir = "DESC"

        select_query += f" ORDER BY {field} {sort_dir}"

    if limit is not None:
        select_query += f" LIMIT {limit}"

    if offset is not None:
        select_query += f" OFFSET {offset}"

    return {"select": select_query, "total_count": count_query}


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
        sql_queries = __build_last_incidents_query(
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

        total_count = session.exec(text(sql_queries.get("total_count"))).scalar()
        all_records = session.exec(text(sql_queries.get("select"))).all()
        incidents = [Incident(**row._asdict()) for row in all_records]

        if with_alerts:
            enrich_incidents_with_alerts(tenant_id, incidents, session)

    return incidents, total_count


class FacetOptionDto(BaseModel):
    display_name: str
    value: Any
    matches_count: int


class FacetDto(BaseModel):
    id: str
    property_path: str
    name: str
    description: Optional[str]
    is_static: bool
    is_lazy: bool = True
    type: FacetType

class CreateFacetDto(BaseModel):
    property_path: str
    name: str
    description: Optional[str]

def build_facets_data_query(
    tenant_id: str, facets_to_load: list[FacetDto], allowed_incident_ids: list[str]
) -> str:
    facet_fields = [
        {
            "facet_name": facet.property_path,
            "facet_id": facet.id,
            "metadata": known_fields.get(facet.property_path) or known_fields.get("*"),
        }
        for facet in facets_to_load
    ]

    # Defining the CTE: incident_alerts
    incident_alerts_cte = (
        select(
            LastAlertToIncident.incident_id.label("incident_id"),
            AlertEnrichment.enrichments.label("enrichments"),
            Alert.event.label("event"),
            Alert.provider_type.label("incident_alert_provider_type"),
        )
        .join(
            LastAlert,
            and_(
                LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                LastAlert.fingerprint == LastAlertToIncident.fingerprint,
            ),
        )
        .join(Alert, LastAlert.alert_id == Alert.id)
        .outerjoin(
            AlertEnrichment, Alert.fingerprint == AlertEnrichment.alert_fingerprint
        )
    )

    if allowed_incident_ids:
        incident_alerts_cte = incident_alerts_cte.filter(
            LastAlertToIncident.incident_id.in_(allowed_incident_ids)
        )

    incident_alerts_cte = incident_alerts_cte.cte("incident_alerts")

    # Defining the CTE: all_incidents
    all_incidents_cte = (
        select(
            Incident,
            Incident.id.label("entity_id"),
            incident_alerts_cte.c.event,
            incident_alerts_cte.c.enrichments,
        )
        .outerjoin(
            incident_alerts_cte, Incident.id == incident_alerts_cte.c.incident_id
        )
        .filter(Incident.tenant_id == tenant_id)
    )

    if allowed_incident_ids:
        all_incidents_cte = all_incidents_cte.filter(
            Incident.id.in_(allowed_incident_ids)
        )

    all_incidents_cte = all_incidents_cte.cte("all_incidents")

    # Main Query: JSON Extraction and Counting
    union_queries = []

    for facet_field in facet_fields:
        facet_name = facet_field["facet_name"]
        metadata = facet_field["metadata"]
        group_by_exp = None

        if metadata.get("type") == "json":
            group_by_exp = func.json_unquote(
                func.json_extract(
                    literal_column("all_incidents.event"), f"$.{facet_name}"
                )
            )
        else:
            group_by_exp = literal_column(facet_name)

        union_queries.append(
            select(
                literal(facet_name).label("facet_name"),
                group_by_exp.label("facet_value"),
                func.count(func.distinct(literal_column("entity_id"))).label(
                    "matches_count"
                ),
            )
            .select_from(all_incidents_cte)
            .group_by(group_by_exp)
        )

    query = None

    if len(union_queries) > 1:
        query = union_queries[0].union(*union_queries[1:])
    else:
        query = union_queries[0]

    return query


static_facets = [
    FacetDto(
        id="status",
        property_path="status",
        name="Status",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="serverity",
        property_path="serverity",
        name="Severity",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="assignee",
        property_path="assignee",
        name="Assignee",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="service",
        property_path="service",
        name="Service",
        is_static=True,
        type=FacetType.str
    ),
    FacetDto(
        id="sources",
        property_path="sources",
        name="Source",
        is_static=True,
        type=FacetType.str
    )
]
static_facets_dict = {facet.id: facet for facet in static_facets}

def get_facets(tenant_id: str, entity_type: str, facet_ids_to_load: list[str] = None) -> list[FacetDto]:
    with Session(engine) as session:
        query = session.query(
            Facet
        ).filter(Facet.tenant_id == tenant_id).filter(Facet.entity_type == entity_type)

        if facet_ids_to_load:
            query = query.filter(Facet.id.in_([UUID(id) for id in facet_ids_to_load]))

        facets_from_db: list[Facet] = query.all()

        facet_dtos = []

        for facet in facets_from_db:
            facet_dtos.append(
                FacetDto(
                    id=str(facet.id),
                    property_path=facet.property_path,
                    name=facet.name,
                    is_static=False,
                    is_lazy=True,
                    type=FacetType.str
                )
            )

        return facet_dtos

def get_incident_facets_data(
    tenant_id: str, facets_to_load: list[str], allowed_incident_ids: list[str]
) -> dict[str, list[FacetOptionDto]]:
    try:        
        if facets_to_load:
            facets = get_incident_facets(tenant_id, facets_to_load)
        else:
            facets = static_facets

        facet_name_to_id_dict = {facet.property_path: facet.id for facet in facets}

        db_query = build_facets_data_query(
            tenant_id=tenant_id,
            facets_to_load=facets,
            allowed_incident_ids=allowed_incident_ids,
        )
        with Session(engine) as session:
            data = session.exec(db_query).all()
            result_dict = {}

            for facet_name, facet_value, matches_count in data:
                facet_id = facet_name_to_id_dict.get(facet_name, facet_name)
    
                if facet_id not in result_dict:
                    result_dict[facet_id] = []

                result_dict[facet_id].append(
                    FacetOptionDto(
                        display_name=str(facet_value),
                        value=facet_value,
                        matches_count=matches_count,
                    )
                )

            return result_dict
    except Exception as e:
        print(e)
        print("f")
        raise e

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

def create_facet(tenant_id: str, facet: CreateFacetDto) -> FacetDto:
    with Session(engine) as session:
        facet_db = Facet(
            id=str(uuid4()),
            tenant_id=tenant_id,
            name=facet.name,
            description=facet.description,
            entity_type="incident",
            property_path=facet.property_path,
            type=FacetType.str.value,
            user_id="system"

        )
        session.add(facet_db)
        session.commit()
        return FacetDto(
            id=str(facet_db.id),
            property_path=facet_db.property_path,
            name=facet_db.name,
            description=facet_db.description,
            is_static=False,
            is_lazy=True,
            type=facet_db.type
        )
    return None


def delete_facet(tenant_id: str, facet_id: str) -> bool:
    with Session(engine) as session:
        facet = (
            session.query(Facet)
            .filter(Facet.tenant_id == tenant_id)
            .filter(Facet.id == UUID(facet_id))
            .first()
        )
        if facet:
            session.delete(facet)
            session.commit()
            return True
        return False
