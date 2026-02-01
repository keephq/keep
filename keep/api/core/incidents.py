"""
Facet utilities:
- CRUD for Facet records
- Generating facet option lists via query-builder
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.exc import OperationalError
from sqlalchemy import select
from sqlmodel import Session

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata
from keep.api.core.facets_query_builder.get_facets_query_builder import (
    get_facets_query_builder,
)
from keep.api.core.facets_query_builder.utils import get_facet_key
from keep.api.core.db import engine
from keep.api.models.db.facet import Facet, FacetType
from keep.api.models.facet import (
    CreateFacetDto,
    FacetDto,
    FacetOptionDto,
    FacetOptionsQueryDto,
)

logger = logging.getLogger(__name__)

OPTIONS_PER_FACET = 50


def _to_uuid(value: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except Exception as e:
        raise ValueError(f"Invalid UUID: {value}") from e


def map_facet_option_value(value: Any, data_type: DataType) -> Any:
    """
    Maps string-ish option values into the correct type based on field metadata.
    """
    if value is None:
        return None

    # Many SQL dialects return everything as str for JSON extracts.
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
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return value

    return value


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
    invalid_facets: List[FacetDto] = []
    valid_facets: List[FacetDto] = []

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
        except OperationalError as e:
            logger.warning(
                "Failed to execute query for facet options. facet_options_query=%s error=%s",
                json.dumps(facet_options_query.dict()),
                str(e),
            )
            return result

    # Group rows by facet key (not necessarily facet.id).
    grouped: Dict[str, list] = {}
    for row in rows:
        # Expected row shape from builder: (facet_key, facet_value, matches_count) or
        # an object with those attributes. Make it tolerant.
        facet_id = getattr(row, "facet_id", None)
        facet_value = getattr(row, "facet_value", None)
        matches_count = getattr(row, "matches_count", None)

        if facet_id is None and isinstance(row, (tuple, list)) and len(row) >= 3:
            facet_id, facet_value, matches_count = row[0], row[1], row[2]

        if facet_id is None:
            continue

        grouped.setdefault(facet_id, [])

        # SQLite option limit guard (subquery LIMIT limitations)
        if engine.dialect.name == "sqlite" and len(grouped[facet_id]) >= OPTIONS_PER_FACET:
            continue

        grouped[facet_id].append((facet_id, facet_value, matches_count))

    # Build final options list per facet
    for facet in facets:
        property_meta = properties_metadata.get_property_metadata_for_str(facet.property_path)
        if property_meta is None:
            result[facet.id] = []
            continue

        # Key used by query-builder can differ from facet.id, so compute it.
        facet_query = None
        if facet_options_query and facet_options_query.facet_queries:
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
                    value=map_facet_option_value(val, property_meta.data_type),
                    matches_count=0 if cnt is None else cnt,
                )
                for (_fid, val, cnt) in grouped[facet_key]
            ]

        # If enum values exist, ensure all enum values are present with 0 matches.
        if property_meta.enum_values:
            existing_values = {o.value for o in options}
            for enum_val in property_meta.enum_values:
                if enum_val not in existing_values:
                    options.append(
                        FacetOptionDto(
                            display_name=str(enum_val),
                            value=enum_val,
                            matches_count=0,
                        )
                    )

            # Keep enum-defined ordering, unknowns go last.
            enum_index = {v: i for i, v in enumerate(property_meta.enum_values)}
            options.sort(key=lambda o: enum_index.get(o.value, 10_000))

        result[facet.id] = options

    # Invalid facets return empty list already via initialization.
    for bad in invalid_facets:
        result[bad.id] = []

    return result


def create_facet(tenant_id: str, entity_type: str, facet: CreateFacetDto) -> FacetDto:
    """
    Create a new facet and return FacetDto.
    """
    with Session(engine) as session:
        facet_db = Facet(
            id=_to_uuid(str(uuid4())),
            tenant_id=tenant_id,
            name=facet.name,
            description=facet.description,
            entity_type=entity_type,
            property_path=facet.property_path,
            type=FacetType.str,  # store enum, not .value strings unless model expects string
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
    """
    Delete a facet, return True if deleted.
    """
    facet_uuid = _to_uuid(facet_id)

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

        facets = session.exec(query).all()

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
            for f in facets
        ]