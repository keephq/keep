import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    PropertiesMetadata,
    PropertyMetadataInfo,
)
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider,
)
from keep.api.core.db import engine
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
from keep.api.models.query import QueryDto, SortOptionsDto

logger = logging.getLogger(__name__)

ALERTS_HARD_LIMIT = int(os.environ.get("KEEP_LAST_ALERTS_LIMIT", 50000))
FACET_OPTIONS_LIMIT = 50

# Known patterns that indicate the frontend builder failed and returned a tautology.
QUERY_BUILDER_FAILURE_PATTERNS = {"1 == 1", "1==1", "true", "TRUE"}


alerts_hard_limit = ALERTS_HARD_LIMIT  # keep legacy name if referenced elsewhere


def _truthy_str(s: Optional[str]) -> bool:
    return bool(s and str(s).strip())


def _normalize_cel(cel: Optional[str]) -> str:
    if not cel:
        return ""
    return " ".join(cel.split())


def _apply_cel_sql_filter(sql_query, sql_filter: Optional[str], *, tenant_id: str, cel: str):
    """
    Minimal mitigation wrapper for raw SQL filter application.
    If your CEL converter can return bind params, upgrade this to bindparams safely.
    """
    if not sql_filter:
        return sql_query
    try:
        return sql_query.where(text(sql_filter))
    except Exception:
        logger.error(
            "Failed to apply CEL SQL filter",
            extra={"tenant_id": tenant_id, "cel": cel, "sql_filter": sql_filter},
            exc_info=True,
        )
        raise


# --- field mapping config (kept close to your original, but cleaned a bit) ---

alert_field_configurations = [
    FieldMappingConfiguration(map_from_pattern="id", map_to="lastalert.alert_id", data_type=DataType.UUID),
    FieldMappingConfiguration(map_from_pattern="source", map_to="alert.provider_type", data_type=DataType.STRING),
    FieldMappingConfiguration(map_from_pattern="providerId", map_to="alert.provider_id", data_type=DataType.STRING),
    FieldMappingConfiguration(map_from_pattern="providerType", map_to="alert.provider_type", data_type=DataType.STRING),
    FieldMappingConfiguration(map_from_pattern="timestamp", map_to="lastalert.timestamp", data_type=DataType.DATETIME),
    FieldMappingConfiguration(map_from_pattern="fingerprint", map_to="lastalert.fingerprint", data_type=DataType.STRING),
    FieldMappingConfiguration(map_from_pattern="startedAt", map_to="lastalert.first_timestamp", data_type=DataType.DATETIME),

    FieldMappingConfiguration(map_from_pattern="incident.id", map_to=["incident.id"], data_type=DataType.UUID),
    FieldMappingConfiguration(map_from_pattern="incident.is_visible", map_to=["incident.is_visible"], data_type=DataType.BOOLEAN),
    FieldMappingConfiguration(
        map_from_pattern="incident.name",
        map_to=["incident.user_generated_name", "incident.ai_generated_name"],
        data_type=DataType.STRING,
    ),

    FieldMappingConfiguration(
        map_from_pattern="severity",
        map_to=["JSON(alertenrichment.enrichments).*", "JSON(alert.event).*"],
        enum_values=[s.value for s in sorted(AlertSeverity, key=lambda x: x.order)],
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="lastReceived",
        map_to=["JSON(alertenrichment.enrichments).*", "JSON(alert.event).*"],
        data_type=DataType.DATETIME,
    ),
    FieldMappingConfiguration(
        map_from_pattern="status",
        map_to=["JSON(alertenrichment.enrichments).*", "JSON(alert.event).*"],
        enum_values=list(reversed([s.value for s in AlertStatus])),
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="dismissed",
        map_to=["JSON(alertenrichment.enrichments).*"],
        data_type=DataType.BOOLEAN,
    ),
    FieldMappingConfiguration(
        map_from_pattern="firingCounter",
        map_to=["JSON(alertenrichment.enrichments).*", "JSON(alert.event).*"],
        data_type=DataType.INTEGER,
    ),
    FieldMappingConfiguration(
        map_from_pattern="unresolvedCounter",
        map_to=["JSON(alertenrichment.enrichments).*", "JSON(alert.event).*"],
        data_type=DataType.INTEGER,
    ),
    FieldMappingConfiguration(
        map_from_pattern="*",
        map_to=["JSON(alertenrichment.enrichments).*", "JSON(alert.event).*"],
        data_type=DataType.STRING,
    ),
]

# add alert.* prefixed variants
field_configurations_with_alert_prefix = [
    FieldMappingConfiguration(
        map_from_pattern=f"alert.{item.map_from_pattern}",
        map_to=item.map_to,
        data_type=item.data_type,
        enum_values=item.enum_values,
    )
    for item in alert_field_configurations
]
alert_field_configurations = field_configurations_with_alert_prefix + alert_field_configurations

properties_metadata = PropertiesMetadata(alert_field_configurations)

static_facets = [
    FacetDto(id="f8a91ac7-4916-4ad0-9b46-a5ddb85bfbb8", property_path="severity", name="Severity", is_static=True, type=FacetType.str),
    FacetDto(id="5dd1519c-6277-4109-ad95-c19d2f4f15e3", property_path="status", name="Status", is_static=True, type=FacetType.str),
    FacetDto(id="461bef05-fc20-4363-b427-9d26fe064e7f", property_path="source", name="Source", is_static=True, type=FacetType.str),
    FacetDto(id="6afa12d7-21df-4694-8566-fd56d5ee2266", property_path="incident.name", name="Incident", is_static=True, type=FacetType.str),
    FacetDto(id="77b8a6d4-3b8d-4b6a-9f8e-2c8e4b8f8e4c", property_path="dismissed", name="Dismissed", is_static=True, type=FacetType.str),
]
static_facets_dict = {facet.id: facet for facet in static_facets}


def get_threshold_query(tenant_id: str):
    """
    Returns the timestamp threshold for the "last alerts" hard cap window.
    """
    return func.coalesce(
        select(LastAlert.timestamp)
        .select_from(LastAlert)
        .where(LastAlert.tenant_id == tenant_id)
        .order_by(LastAlert.timestamp.desc())
        .limit(1)
        .offset(ALERTS_HARD_LIMIT - 1)
        .scalar_subquery(),
        # SQLite may not like datetime.min with tz; keep it simple
        datetime.datetime(1, 1, 1),
    )


def __build_query_for_filtering(
    tenant_id: str,
    select_args: list,
    cel: Optional[str] = None,
    fetch_alerts_data: bool = True,
    fetch_incidents: bool = False,
    force_fetch: bool = False,
) -> Dict[str, Any]:
    cel = _normalize_cel(cel)
    cel_to_sql_instance = get_cel_to_sql_provider(properties_metadata)

    sql_filter: Optional[str] = None
    involved_fields: list = []
    fetch_incidents = bool(fetch_incidents or (cel and "incident." in cel))

    if cel:
        cel_to_sql_result = cel_to_sql_instance.convert_to_sql_str_v2(cel)
        sql_filter = cel_to_sql_result.sql
        involved_fields = cel_to_sql_result.involved_fields or []
        # determine if incidents are needed based on involved fields
        fetch_incidents = any(
            getattr(field, "field_name", "").startswith("incident.")
            for field in involved_fields
        ) or fetch_incidents

    sql_query = select(*select_args).select_from(LastAlert)

    if fetch_alerts_data or force_fetch:
        sql_query = (
            sql_query.join(
                Alert,
                and_(Alert.id == LastAlert.alert_id, Alert.tenant_id == LastAlert.tenant_id),
            )
            .outerjoin(
                AlertEnrichment,
                and_(
                    LastAlert.tenant_id == AlertEnrichment.tenant_id,
                    LastAlert.fingerprint == AlertEnrichment.alert_fingerprint,
                ),
            )
        )

    if fetch_incidents or force_fetch:
        # clean, tenant-safe incident join: only FIRING incidents join through
        sql_query = (
            sql_query.outerjoin(
                LastAlertToIncident,
                and_(
                    LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                    LastAlert.fingerprint == LastAlertToIncident.fingerprint,
                ),
            )
            .outerjoin(
                Incident,
                and_(
                    Incident.tenant_id == tenant_id,
                    LastAlertToIncident.tenant_id == Incident.tenant_id,
                    LastAlertToIncident.incident_id == Incident.id,
                    Incident.status == IncidentStatus.FIRING.value,
                ),
            )
        )

    sql_query = (
        sql_query.where(LastAlert.tenant_id == tenant_id)
        .where(LastAlert.timestamp >= get_threshold_query(tenant_id))
    )

    sql_query = _apply_cel_sql_filter(sql_query, sql_filter, tenant_id=tenant_id, cel=cel)

    return {
        "query": sql_query,
        "involved_fields": involved_fields,
        "fetch_incidents": fetch_incidents,
    }


def build_total_alerts_query(tenant_id: str, query: QueryDto):
    cel = _normalize_cel(query.cel)
    fetch_incidents = bool(cel and "incident." in cel)
    fetch_alerts_data = _truthy_str(cel)

    count_expr = func.count(func.distinct(LastAlert.alert_id)) if fetch_incidents else func.count(1)

    built = __build_query_for_filtering(
        tenant_id=tenant_id,
        cel=cel,
        select_args=[count_expr],
        fetch_alerts_data=fetch_alerts_data,
        fetch_incidents=fetch_incidents,
    )
    return built["query"]


def build_alerts_query(tenant_id: str, query: QueryDto):
    cel_to_sql_instance = get_cel_to_sql_provider(properties_metadata)

    sort_pairs = [(s.sort_by, s.sort_dir) for s in (query.sort_options or [])]
    sort_by_exp = cel_to_sql_instance.get_order_by_expression(sort_pairs)

    distinct_columns = [
        text(cel_to_sql_instance.get_field_expression(s.sort_by))
        for s in (query.sort_options or [])
    ]

    built = __build_query_for_filtering(
        tenant_id=tenant_id,
        select_args=[Alert, AlertEnrichment, LastAlert.first_timestamp.label("firstTimestamp")] + distinct_columns,
        cel=_normalize_cel(query.cel),
        fetch_alerts_data=True,  # data query needs alert columns
    )

    sql_query = built["query"].order_by(text(sort_by_exp))
    fetch_incidents = built["fetch_incidents"]

    if fetch_incidents:
        sql_query = sql_query.distinct(*(distinct_columns + [Alert.id]))

    if query.limit is not None:
        sql_query = sql_query.limit(query.limit)
    if query.offset is not None:
        sql_query = sql_query.offset(query.offset)

    return sql_query


def query_last_alerts(tenant_id: str, query: QueryDto) -> Tuple[List[Alert], int]:
    q = query.copy()

    # normalize frontend failure patterns
    if q.cel and _normalize_cel(q.cel) in QUERY_BUILDER_FAILURE_PATTERNS:
        logger.error("Frontend query builder returned invalid CEL", extra={"tenant_id": tenant_id, "cel": q.cel})
        q.cel = ""

    if q.limit is None:
        q.limit = 1000
    if q.offset is None:
        q.offset = 0

    # clamp hard limits early (before DB work)
    if q.offset >= ALERTS_HARD_LIMIT:
        return [], 0

    if q.limit <= 0:
        return [], 0

    max_limit = ALERTS_HARD_LIMIT - q.offset
    if q.limit > max_limit:
        q.limit = max_limit

    if q.sort_by is not None:
        q.sort_options = [SortOptionsDto(sort_by=q.sort_by, sort_dir=q.sort_dir)]
    if not q.sort_options:
        q.sort_options = [SortOptionsDto(sort_by="timestamp", sort_dir="desc")]

    with Session(engine) as session:
        try:
            total_count_query = build_total_alerts_query(tenant_id=tenant_id, query=q)
            total_count = session.exec(total_count_query).one()[0]

            data_query = build_alerts_query(tenant_id, q)
            rows = session.execute(data_query).all()

        except OperationalError as e:
            logger.error(
                "DB operational error while querying alerts",
                extra={"tenant_id": tenant_id, "query": q.dict(exclude_unset=True)},
                exc_info=True,
            )
            # If you prefer hard-fail, raise. Keeping your existing behavior:
            return [], 0

    alerts: List[Alert] = []
    for alert_obj, enrichment_obj, first_ts, *rest in rows:
        alert: Alert = alert_obj
        alert.alert_enrichment = enrichment_obj

        # keep event schema consistent
        alert.event = alert.event or {}
        alert.event["firstTimestamp"] = str(first_ts) if first_ts is not None else alert.event.get("firstTimestamp")
        # optionally also provide startedAt for backwards compat
        alert.event.setdefault("startedAt", alert.event.get("firstTimestamp"))

        alert.event["event_id"] = str(alert.id)
        alerts.append(alert)

    return alerts, total_count


def get_alert_facets_data(
    tenant_id: str,
    facet_options_query: FacetOptionsQueryDto,
) -> dict[str, list[FacetOptionDto]]:
    if facet_options_query and facet_options_query.facet_queries:
        facets = get_alert_facets(tenant_id, list(facet_options_query.facet_queries.keys()))
    else:
        facets = static_facets

    def base_query_factory(
        facet_property_path: str,
        involved_fields: PropertyMetadataInfo,
        select_statement,
    ):
        fetch_incidents = (
            "incident." in facet_property_path
            or any("incident." in getattr(item, "field_name", "") for item in involved_fields or [])
        )
        return __build_query_for_filtering(
            tenant_id=tenant_id,
            select_args=select_statement,
            fetch_incidents=fetch_incidents,
            fetch_alerts_data=False,
        )["query"]

    return get_facet_options(
        base_query_factory=base_query_factory,
        entity_id_column=LastAlert.alert_id,
        facets=facets,
        facet_options_query=facet_options_query,
        properties_metadata=properties_metadata,
    )


def get_alert_facets(tenant_id: str, facet_ids_to_load: Optional[list[str]] = None) -> list[FacetDto]:
    if not facet_ids_to_load:
        return static_facets + get_facets(tenant_id, "alert")

    facets: list[FacetDto] = []
    not_static: list[str] = []

    for facet_id in facet_ids_to_load:
        facet = static_facets_dict.get(facet_id)
        if facet is None:
            not_static.append(facet_id)
        else:
            facets.append(facet)

    if not_static:
        facets += get_facets(tenant_id, "alert", not_static)

    return facets


def get_alert_potential_facet_fields(tenant_id: str) -> list[str]:
    with Session(engine) as session:
        q = (
            select(AlertField.field_name)
            .select_from(AlertField)
            .where(AlertField.tenant_id == tenant_id)
            .distinct()
        )
        result = session.exec(q).all()
        # for single-column scalar queries, this is already a list[str] in many setups;
        # keep it safe and simple:
        return [r[0] if isinstance(r, (tuple, list)) else r for r in result]