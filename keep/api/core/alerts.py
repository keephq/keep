import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    and_,
    desc,
    literal_column,
    select,
)
from sqlmodel import Session, select, text


# This import is required to create the tables
from keep.api.core.facets import get_facet_options, get_facets
from keep.api.models.db.alert import Alert, AlertEnrichment, Incident, LastAlert, LastAlertToIncident
from keep.api.models.db.facet import FacetType
from keep.api.models.facet import FacetDto, FacetOptionDto
from keep.api.core.db import engine
from keep.api.core.cel_to_sql.properties_metadata import FieldMappingConfiguration, PropertiesMetadata
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import get_cel_to_sql_provider_for_dialect

logger = logging.getLogger(__name__)

alert_field_configurations = [
    FieldMappingConfiguration("provider_type", "provider_type"),
    FieldMappingConfiguration("provider_id", "provider_id"),
    FieldMappingConfiguration(map_from_pattern = "incident.name", map_to=['incident.user_generated_name', 'incident.ai_generated_name']),
    FieldMappingConfiguration(map_from_pattern = "*", map_to=["alert_enrichment_json", "event"], is_json=True),
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
        property_path="provider_type",
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

def __build_base_query(
    tenant_id,
):
    base_query_cte = (
        select(
            AlertEnrichment,
            LastAlert.alert_id,
            LastAlert.tenant_id.label("last_alert_tenant_id"),
            AlertEnrichment.enrichments.label('alert_enrichment_json'),
            LastAlert.first_timestamp.label("startedAt"),
        )
        .select_from(LastAlert)
        # .join(
        #     Alert,
        #     and_(
        #         LastAlert.tenant_id == Alert.tenant_id, LastAlert.alert_id == Alert.id
        #     ),
        # )
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
    ).cte("base_query")

    return (
        select(
            AlertEnrichment,
            Alert,
            Alert.id.label('entity_id'),
            literal_column('alert_enrichment_json'),
            literal_column('startedAt'),
        )
        .select_from(base_query_cte)
        .join(
            Alert,
            and_(
                base_query_cte.c.last_alert_tenant_id == Alert.tenant_id, base_query_cte.c.alert_id == Alert.id
            ),
        )
    )

def build_alerts_query(
        dialect_name: str,
        tenant_id,
        provider_id=None,
        limit=1000,
        timeframe=None,
        upper_timestamp=None,
        lower_timestamp=None,
        with_incidents=False,
        fingerprints=None,
        cel=None
    ):
    base_query_cte = __build_base_query(tenant_id)

    stmt = base_query_cte

    # db.get_last_alerts(
    #     tenant_id,
    #     provider_id=None,
    #     limit=1000,
    #     timeframe=None,
    #     upper_timestamp=None,
    #     lower_timestamp=None,
    #     with_incidents=False,
    #     fingerprints=None
    # )

    if timeframe:
        stmt = stmt.where(
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
        stmt = stmt.where(*filter_conditions)

    if provider_id:
        stmt = stmt.where(Alert.provider_id == provider_id)

    if cel:
        cel_to_sql_provider_type = get_cel_to_sql_provider_for_dialect(dialect_name)
        instance = cel_to_sql_provider_type(properties_metadata)
        sql_filter = instance.convert_to_sql_str(cel)
        stmt = stmt.where(text(sql_filter))

    # Order by timestamp in descending order and limit the results
    stmt = stmt.order_by(desc(Alert.timestamp)).limit(limit)
    steq = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    return stmt

def get_last_alerts(
    tenant_id,
    provider_id=None,
    limit=1000,
    timeframe=None,
    upper_timestamp=None,
    lower_timestamp=None,
    with_incidents=False,
    fingerprints=None,
    cel=None
) -> list[Alert]:
    with Session(engine) as session:
        dialect_name = session.bind.dialect.name

        query = build_alerts_query(
            dialect_name,
            tenant_id,
            provider_id,
            limit,
            timeframe,
            upper_timestamp,
            lower_timestamp,
            with_incidents,
            fingerprints,
            cel
        )

        # Execute the query
        start_time = datetime.now()
        alerts_with_start = session.execute(query).all()
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        logger.info(f"Query execution time: {execution_time} seconds")

        # Process results based on dialect
        alerts = []
        for alert_data in alerts_with_start:
            alert: Alert = alert_data[1]
            startedAt = alert_data.startedAt
            alert_enrichment = alert_data[0]
            alert.alert_enrichment = alert_enrichment
            alert.event["startedAt"] = str(startedAt)
            alert.event["event_id"] = str(alert.id)
            
            alerts.append(alert)

        return alerts


def get_alert_facets_data(
    tenant_id: str,
    facets_query: dict[str, str],
) -> dict[str, list[FacetOptionDto]]:
    if facets_query:
        facets = get_alert_facets(tenant_id, facets_query.keys())
    else:
        facets = static_facets

    base_query_cte = __build_base_query(tenant_id).cte("alerts_query")
    base_query = select(base_query_cte)

    return get_facet_options(
        base_query=base_query,
        facets=facets,
        facets_query=facets_query,
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