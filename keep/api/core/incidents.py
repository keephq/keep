"""
Facet utilities:
- CRUD for Facet records
- Generating facet option lists via query-builder
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata
from keep.api.core.db import engine
from keep.api.core.facets_query_builder.get_facets_query_builder import (
    get_facets_query_builder,
)
from keep.api.core.facets_query_builder.utils import get_facet_key
from keep.api.models.db.facet import Facet, FacetType
from keep.api.models.facet import CreateFacetDto, FacetDto, FacetOptionDto, FacetOptionsQueryDto

logger = logging.getLogger(__name__)

OPTIONS_PER_FACET = 50


def _to_uuid(value: Any) -> UUID:
    """
    Convert value into UUID or raise ValueError with a clean message.
    """
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except Exception as e:
        raise ValueError(f"Invalid UUID: {value}") from e


def _safe_json(obj: Any) -> str:
    """
    Never let logging crash the request.
    """
    try:
        return json.dumps(obj, default=str)
    except Exception:
        return str(obj)


def _normalize_bool(value: Any) -> Any:
    """
    Normalize common DB-returned boolean representations.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "t"}
    return value


def map_facet_option_value(value: Any, data_type: DataType) -> Any:
    """
    Maps string-ish option values into the correct type based on field metadata.
    """
    if value is None:
        return None

    if data_type == DataType.INTEGER:
        try:
            return int(value)
        except Exception:
            return value

    if data_type == DataType.FLOAT:
        try:
            return float(value)
        except Exception:
            return value

    if data_type == DataType.BOOLEAN:
        return _normalize_bool(value)

    return value


def _extract_builder_row(row: Any) -> Optional[Tuple[str, Any, Optional[int]]]:
    """
    Builder row may be:
      - object with attrs: facet_id/facet_key, facet_value, matches_count
      - tuple/list: (key, value, count) or (key, value, count, ...)
    Returns: (key, value, count) where key is the facet-key used by builder.
    """
    # Attribute-based shape
    key = getattr(row, "facet_id", None)  # some builders call it facet_id
    if key is None:
        key = getattr(row, "facet_key", None)  # some builders call it facet_key

    value = getattr(row, "facet_value", None)
    count = getattr(row, "matches_count", None)

    if key is not None:
        return str(key), value, count

    # Tuple/list shape
    if isinstance(row, (tuple, list)) and len(row) >= 2:
        key = row[0]
        value = row[1]
        count = row[2] if len(row) >= 3 else None
        return str(key), value, count

    return None


def get_facet_options(
    base_query_factory: Callable[[str, Any, Any], Any],
    entity_id_column: Any,
    facets: List[FacetDto],
    facet_options_query: FacetOptionsQueryDto,
    properties_metadata: PropertiesMetadata,
) -> Dict[str, List[FacetOptionDto]]:
    """
    Returns dict: {facet_id: [FacetOptionDto...]} for each requested facet.
    """
    # Initialize all facets as empty by default
    result: Dict[str, List[FacetOptionDto]] = {f.id: [] for f in facets}

    # Partition facets into valid/invalid based on metadata existence
    valid_facets: List[FacetDto] = []
    for facet in facets:
        if properties_metadata.get_property_metadata_for_str(facet.property_path):
            valid_facets.append(facet)

    if not valid_facets:
        return result

    # Execute builder query
    try:
        with Session(engine) as session:
            db_query = get_facets_query_builder(properties_metadata).build_facets_data_query(
                base_query_factory=base_query_factory,
                entity_id_column=entity_id_column,
                facets=valid_facets,
                facet_options_query=facet_options_query,
            )
            rows = session.exec(db_query).all()
    except SQLAlchemyError as e:
        logger.warning(
            "Failed to execute facet options query. facet_options_query=%s error=%s",
            _safe_json(getattr(facet_options_query, "dict", lambda: facet_options_query)()),
            str(e),
        )
        return result

    # Group rows by the key emitted by builder (facet_key), not by facet.id.
    grouped: Dict[str, List[Tuple[Any, Optional[int]]]] = {}
    for row in rows:
        extracted = _extract_builder_row(row)
        if not extracted:
            continue
        key, value, count = extracted

        grouped.setdefault(key, [])
        if engine.dialect.name == "sqlite" and len(grouped[key]) >= OPTIONS_PER_FACET:
            continue
        grouped[key].append((value, count))

    # Build result per facet using computed facet_key
    for facet in facets:
        prop_meta = properties_metadata.get_property_metadata_for_str(facet.property_path)
        if prop_meta is None:
            result[facet.id] = []
            continue

        facet_query = None
        if facet_options_query and getattr(facet_options_query, "facet_queries", None):
            facet_query = facet_options_query.facet_queries.get(facet.id)

        facet_key = get_facet_key(
            facet.property_path,
            getattr(facet_options_query, "cel", None),
            facet_query,
        )

        options: List[FacetOptionDto] = []

        if facet_key in grouped:
            options = [
                FacetOptionDto(
                    display_name=str(val),
                    value=map_facet_option_value(val, prop_meta.data_type),
                    matches_count=0 if cnt is None else cnt,
                )
                for (val, cnt) in grouped[facet_key]
            ]

        # Ensure enum values appear, even if no matches
        if prop_meta.enum_values:
            existing_values = {o.value for o in options}
            for enum_val in prop_meta.enum_values:
                if enum_val not in existing_values:
                    options.append(
                        FacetOptionDto(
                            display_name=str(enum_val),
                            value=enum_val,
                            matches_count=0,
                        )
                    )

            # Stable enum ordering; unknown values go last
            enum_index = {v: i for i, v in enumerate(prop_meta.enum_values)}
            options.sort(key=lambda o: enum_index.get(o.value, 10_000))

        result[facet.id] = options

    return result


def _facet_type_for_db() -> Any:
    """
    Normalize FacetType storage.
    If the model expects a string, use `.value`.
    If it expects Enum, passing the enum is fine.
    We can't reliably introspect SQLModel field type here without importing internals,
    so we pick the safest behavior: prefer `.value` if it exists.
    """
    # FacetType likely an Enum with .value; use that unless you KNOW column is Enum.
    return FacetType.str.value if hasattr(FacetType.str, "value") else FacetType.str


def create_facet(tenant_id: str, entity_type: str, facet: CreateFacetDto) -> FacetDto:
    """
    Create a new facet and return FacetDto.
    """
    with Session(engine) as session:
        facet_db = Facet(
            id=_to_uuid(uuid4()),
            tenant_id=tenant_id,
            name=facet.name,
            description=getattr(facet, "description", None),
            entity_type=entity_type,
            property_path=facet.property_path,
            type=_facet_type_for_db(),
            user_id="system",
        )
        session.add(facet_db)
        session.commit()
        session.refresh(facet_db)

        return FacetDto(
            id=str(facet_db.id),
            property_path=facet_db.property_path,
            name=facet_db.name,
            description=getattr(facet_db, "description", None),
            is_static=False,
            is_lazy=True,
            type=facet_db.type,
        )


def delete_facet(tenant_id: str, entity_type: str, facet_id: str) -> bool:
    """
    Delete a facet, return True if deleted.
    """
    facet_uuid = _to_uuid(facet_id)

    with Session(engine) as session:
        facet_db = session.exec(
            select(Facet).where(
                Facet.tenant_id == tenant_id,
                Facet.entity_type == entity_type,
                Facet.id == facet_uuid,
            )
        ).first()

        if not facet_db:
            return False

        session.delete(facet_db)
        session.commit()
        return True


def get_facets(
    tenant_id: str,
    entity_type: str,
    facet_ids_to_load: Optional[List[str]] = None,
) -> List[FacetDto]:
    """
    Fetch facets for tenant/entity. Optionally filter by facet ids.
    """
    facet_uuids: Optional[List[UUID]] = None
    if facet_ids_to_load:
        facet_uuids = [_to_uuid(x) for x in facet_ids_to_load]

    with Session(engine) as session:
        query = select(Facet).where(
            Facet.tenant_id == tenant_id,
            Facet.entity_type == entity_type,
        )
        if facet_uuids:
            query = query.where(Facet.id.in_(facet_uuids))

        rows = session.exec(query).all()

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
            for f in rows
        ]