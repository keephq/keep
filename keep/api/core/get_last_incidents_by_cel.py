"""
Keep main database module.

This module contains the CRUD database functions for Keep.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlmodel import Session, text

from keep.api.core.cel_to_sql.sql_providers.sqlite import CelToSqliteProvider

# This import is required to create the tables
from keep.api.models.alert import (
    IncidentSorting,
)

from keep.api.core.db import engine, enrich_incidents_with_alerts
from keep.api.models.db.alert import Incident

known_fields = {
        "provider_type": { # redirects provider_type from cel to alert.provider_type in SQL
            "type": "string",
            "field": "incident_alert_provider_type",
            "mapping_type": "one_to_one"
        },
        "user_generated_name": {
            "type": "string",
            "field": "user_generated_name",
            "mapping_type": "one_to_one"
        },
        "ai_generated_name": {
            "type": "string",
            "field": "ai_generated_name",
            "mapping_type": "one_to_one"
        },
        "user_summary": {
            "type": "string",
            "field": "user_summary",
            "mapping_type": "one_to_one"
        },
        "generated_summary": {
            "type": "string",
            "field": "generated_summary",
            "mapping_type": "one_to_one"
        },
        "assignee": {
            "type": "string",
            "field": "assignee",
            "mapping_type": "one_to_one"
        },
        "severity": {
            "type": "string",
            "field": "severity",
            "mapping_type": "one_to_one"
        },
        "status": {
            "type": "string",
            "field": "status",
            "mapping_type": "one_to_one"
        },
        "creation_time": {
            "type": "datetime",
            "field": "creation_time",
            "mapping_type": "one_to_one"
        },
        "start_time": {
            "type": "datetime",
            "field": "start_time",
            "mapping_type": "one_to_one"
        },
        "end_time": {
            "type": "datetime",
            "field": "end_time",
            "mapping_type": "one_to_one"
        },
        "last_seen_time": {
            "type": "datetime",
            "field": "last_seen_time",
            "mapping_type": "one_to_one"
        },
        "is_predicted": {
            "type": "boolean",
            "field": "is_predicted",
            "mapping_type": "one_to_one"
        },
        "is_confirmed": {
            "type": "boolean",
            "field": "is_confirmed",
            "mapping_type": "one_to_one"
        },
        "alerts_count": {
            "type": "integer",
            "field": "alerts_count",
            "mapping_type": "one_to_one"
        },
        "affected_services": {
            "type": "json",
            "field": "services",
            "mapping_type": "one_to_one"
        },
        "sources": {
            "type": "json",
            "field": "alert_sources",
            "mapping_type": "one_to_one"
        },
        "rule_id": {
            "type": "string",
            "field": "rule_id",
            "mapping_type": "one_to_one"
        },
        "rule_fingerprint": {
            "type": "string",
            "field": "rule_fingerprint",
            "mapping_type": "one_to_one"
        },
        "fingerprint": {
            "type": "string",
            "field": "fingerprint",
            "mapping_type": "one_to_one"
        },
        "same_incident_in_the_past_id": {
            "type": "string",
            "field": "incident_same_incident_in_the_past_id",
            "mapping_type": "one_to_one"
        },
        "merged_into_incident_id": {
            "type": "string",
            "field": "merged_into_incident_id",
            "mapping_type": "one_to_one"
        },
        "merged_at": {
            "type": "datetime",
            "field": "merged_at",
            "mapping_type": "one_to_one"
        },
        "merged_by": {
            "type": "string",
            "field": "merged_by",
            "mapping_type": "one_to_one"
        },
        "*": { # redirects all other fields from cel to merged_json(event + enrichments) in SQL
            "type": "json",
            "field": "merged_json",
            "take_from": ["event", "enrichments"],
        }
    }

def __build_last_incidents_query(
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
    allowed_incident_ids: Optional[List[str]] = None
) -> str:
    instance = CelToSqliteProvider(known_fields_mapping=known_fields)
    query_metadata = instance.convert_to_sql_str(cel)

    where_filter = f"incident.tenant_id = '{tenant_id}' AND incident.is_confirmed = {is_confirmed}"

    if allowed_incident_ids:
        where_filter += f' AND incident.id IN {", ".join(allowed_incident_ids)}'

    if is_predicted is not None:
        where_filter += f' AND incident.is_predicted = {is_predicted}'

    if timeframe:
        where_filter += f' AND incident.start_time >= {datetime.now(tz=timezone.utc) - timedelta(days=timeframe)}'
    
    if upper_timestamp and lower_timestamp:
        where_filter += f' AND (incident.last_seen_time BETWEEN {lower_timestamp} AND {upper_timestamp})'
    elif upper_timestamp:
        where_filter += f' AND incident.last_seen_time <= {upper_timestamp}'
    elif lower_timestamp:
        where_filter += f' AND incident.last_seen_time >= {lower_timestamp}'
    
    if query_metadata.where:
        where_filter += f' AND ({query_metadata.where})'

    sql_cte = f"""
            WITH main AS (
                SELECT 
                    lastalerttoincident.incident_id as incident_id,
                    alertenrichment.enrichments AS enrichments,
                    alert.event AS event,
                    alert.provider_type AS incident_alert_provider_type
                FROM lastalerttoincident
                INNER JOIN lastalert 
                    ON lastalert.tenant_id = lastalerttoincident.tenant_id 
                    AND lastalert.fingerprint = lastalerttoincident.fingerprint 
                INNER JOIN alert 
                    ON lastalert.alert_id = alert.id
                INNER JOIN alertenrichment 
                    ON alert.fingerprint = alertenrichment.alert_fingerprint
                WHERE alert.tenant_id = '{tenant_id}'
            ),

            merged_alerts AS (
                SELECT 
                    main.incident_alert_provider_type AS incident_alert_provider_type,
                    main.incident_id AS incident_id
                    {f',{query_metadata.select_json}' if query_metadata.select_json else ''}
                FROM main
            ),

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
                    {f',{query_metadata.select}' if query_metadata.select else ''}
                FROM 
                    incident
                LEFT JOIN merged_alerts 
                    ON incident.id = merged_alerts.incident_id
                {f'WHERE {where_filter}' if where_filter else ''}
                GROUP BY 
                    incident.id
            )
        """

    select_query = sql_cte + " SELECT * FROM all_incidents"
    count_query = sql_cte + " SELECT COUNT(*) FROM all_incidents"

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

    return {
        "select": select_query,
        "total_count": count_query
    }

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
            tenant_id,
            limit,
            offset,
            timeframe,
            upper_timestamp,
            lower_timestamp,
            is_confirmed,
            sorting,
            is_predicted,
            cel,
            allowed_incident_ids
        )

        total_count = session.exec(text(sql_queries.get("total_count"))).scalar()
        all_records = session.exec(text(sql_queries.get("select"))).all()
        incidents = [Incident(**row._asdict()) for row in all_records]

        if with_alerts:
            enrich_incidents_with_alerts(tenant_id, incidents, session)

    return incidents, total_count
