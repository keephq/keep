import json
import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.facets_query_builder.get_facets_query_builder import (
    get_facets_query_builder,
)
from keep.api.core.facets_query_builder.utils import get_facet_key
from keep.api.core.db import engine
from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata
from keep.api.models.facet import (
    CreateFacetDto,
    FacetDto,
    FacetOptionDto,
    FacetOptionsQueryDto,
)
from keep.api.models.db.facet import Facet, FacetType

logger = logging.getLogger(__name__)

OPTIONS_PER_FACET = 50


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}
    return False


def map_facet_option_value(value: Any, data_type: DataType) -> Any:
    """
    Maps a facet option value to the property data type, best-effort.
    """
    if value is None:
        return None

    try:
        if data_type == DataType.INTEGER:
            return int(value)
        if data_type == DataType.FLOAT:
            return float(value)
        if data_type == DataType.BOOLEAN:
            return _coerce_bool(value)
        return value
    except (ValueError, TypeError):
        # If conversion fails, keep original
        return value


def get_facet_options(
    base_query_factory: Callable[[str, Any], Any],
    entity_id_column: Any,
    facets: List[FacetDto],
    facet_options_query: FacetOptionsQueryDto,
    properties_metadata: PropertiesMetadata,
) -> Dict[str, List[FacetOptionDto]]:
    """
    Returns available facet options per facet id.
    """

    valid_facets: List[FacetDto] = []
    invalid_facets: List[FacetDto] = []

    for facet in facets:
        if properties_metadata.get_property_metadata_for_str(facet.property_path):
            valid_facets.append(facet)
        else:
            invalid_facets.append(facet)

    result: Dict[str, List[FacetOptionDto]] = {f.id: [] for f in facets}

    if not valid_facets:
        return result

    with Session(engine) as session:
        try:
            db_query = get_facets_query_builder(properties_metadata).build_facets_data_query(
                base_query_factory=base_query_factory,
                entity_id_column=entity_id_column,
                facets=valid_facets,
                facet_options_query=facet_options_query,
            )
            rows = session.exec(db_query).all()
        except SQLAlchemyError as e:
            # Safe logging: facet_options_query might contain non-serializable stuff
            try:
                payload = json.dumps(facet_options_query.dict())
            except Exception:
                payload = "<unserializable facet_options_query>"
            logger.warning(
                "Failed to execute facet options query. payload=%s error=%s",
                payload,
                repr(e),
                exc_info=True,
            )
            return result

    # Group rows by the *same key* we later use to read them:
    # facet_key = get_facet_key(property_path, cel, facet_query)
    grouped: Dict[str, List[Any]] = {}

    for row in rows:
        # We assume the query builder returns something with these fields.
        # If it returns tuples, this still works if we index, but prefer named attrs.
        facet_key = getattr(row, "facet_key", None)
        if facet_key is None:
            # Fall back: if builder returned facet_id, we can still group by that,
            # but then lookup must match. We prefer facet_key for correctness.
            facet_key = getattr(row, "facet_id", None)

        if facet_key is None:
            continue

        grouped.setdefault(facet_key, [])

        # SQLite limitation workaround
        if engine.dialect.name == "sqlite" and len(grouped[facet_key]) >= OPTIONS_PER_FACET:
            continue

        grouped[facet_key].append(row)

    # Build result per facet
    for facet in facets:
        prop_meta = properties_metadata.get_property_metadata_for_str(facet.property_path)
        if prop_meta is None:
            result[facet.id] = []
            continue

        facet_query = None
        try:
            # facet_queries might be missing keys; do not crash
            facet_query = facet_options_query.facet_queries.get(facet.id)
        except Exception:
            facet_query = None

        facet_key = get_facet_key(
            facet.property_path,
            facet_options_query.cel,
            facet_query,
        )

        options: List[FacetOptionDto] = []

        if facet_key in grouped:
            for r in grouped[facet_key]:
                # Support either tuple rows or named attributes
                if isinstance(r, tuple) and len(r) >= 3:
                    _, facet_value, matches_count = r[:3]
                else:
                    facet_value = getattr(r, "facet_value", None)
                    matches_count = getattr(r, "matches_count", None)

                options.append(
                    FacetOptionDto(
                        display_name=str(facet_value),
                        value=map_facet_option_value(facet_value, prop_meta.data_type),
                        matches_count=0 if matches_count is None else matches_count,
                    )
                )

        # If enum-backed, append zero-match options not present
        if prop_meta.enum_values:
            present_values = {o.value for o in options}
            for enum_value in prop_meta.enum_values:
                if enum_value not in present_values:
                    options.append(
                        FacetOptionDto(
                            display_name=str(enum_value),
                            value=enum_value,
                            matches_count=0,
                        )
                    )

            # Preserve enum order: first value in enum_values appears first
            enum_order = {v: i for i, v in enumerate(prop_meta.enum_values)}
            options.sort(key=lambda o: enum_order.get(o.value, 10**9))

        result[facet.id] = options

    # invalid facets already empty
    return result


def create_facet(tenant_id: str, entity_type: str, facet: CreateFacetDto) -> FacetDto:
    with Session(engine) as session:
        facet_db = Facet(
            id=uuid4(),  # keep it UUID if DB expects UUID
            tenant_id=tenant_id,
            name=facet.name,
            description=facet.description,
            entity_type=entity_type,
            property_path=facet.property_path,
            type=FacetType.str.value,
            user_id="system",
        )
        session.add(facet_db)
        session.commit()
        session.refresh(facet_db)

        return FacetDto(
            id=str(facet_db.id),
            property_path=facet_db.property_path,
            name=facet_db.name,
            description=facet_db.description,
            is_static=False,
            is_lazy=True,
            type=facet_db.type,
        )


def delete_facet(tenant_id: str, entity_type: str, facet_id: str) -> bool:
    facet_uuid = UUID(facet_id)
    with Session(engine) as session:
        facet = session.exec(
            select(Facet).where(
                Facet.tenant_id == tenant_id,
                Facet.entity_type == entity_type,
                Facet.id == facet_uuid,
            )
        ).first()

        if not facet:
            return False

        session.delete(facet)
        session.commit()
        return True


def get_facets(
    tenant_id: str,
    entity_type: str,
    facet_ids_to_load: Optional[List[str]] = None,
) -> List[FacetDto]:
    with Session(engine) as session:
        query = select(Facet).where(
            Facet.tenant_id == tenant_id,
            Facet.entity_type == entity_type,
        )

        if facet_ids_to_load:
            facet_uuids = [UUID(x) for x in facet_ids_to_load]
            query = query.where(Facet.id.in_(facet_uuids))

        facets_from_db = session.exec(query).all()

        return [
            FacetDto(
                id=str(f.id),
                property_path=f.property_path,
                name=f.name,
                description=getattr(f, "description", None),
                is_static=False,
                is_lazy=True,
                type=f.type,
            )
            for f in facets_from_db
        ]