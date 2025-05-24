import hashlib
import json
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata
from keep.api.core.facets_query_builder.get_facets_query_builder import (
    get_facets_query_builder,
)
from keep.api.models.facet import CreateFacetDto, FacetDto, FacetOptionDto, FacetOptionsQueryDto
from uuid import UUID, uuid4

# from pydantic import BaseModel
from sqlmodel import Session

from keep.api.core.db import engine
from keep.api.models.db.facet import Facet, FacetType

logger = logging.getLogger(__name__)

OPTIONS_PER_FACET = 50


def map_facet_option_value(value, data_type: DataType):
    """
    Maps the value to the appropriate data type.
    Args:
        value: The value to be mapped.
        data_type: The data type to map the value to.
    Returns:
        The mapped value.
    """
    if data_type == DataType.INTEGER:
        try:
            return int(value)
        except ValueError:
            return value
    elif data_type == DataType.FLOAT:
        try:
            return float(value)
        except ValueError:
            return value
    elif data_type == DataType.BOOLEAN:
        return value in ["true", "1"]
    else:
        return value


def get_facet_options(
    base_query_factory: lambda facet_property_path, select_statement: Any,
    entity_id_column: any,
    facets: list[FacetDto],
    facet_options_query: FacetOptionsQueryDto,
    properties_metadata: PropertiesMetadata,
) -> dict[str, list[FacetOptionDto]]:
    """
    Generates facet options based on the provided query and metadata.
    Args:
        base_query: The base SQL query to be used for fetching data.
        cel (str): The CEL (Common Expression Language) string for filtering.
        facets (list[FacetDto]): A list of facet definitions.
        properties_metadata (PropertiesMetadata): Metadata about the properties.
    Returns:
        dict[str, list[FacetOptionDto]]: A dictionary where keys are facet IDs and values are lists of FacetOptionDto objects.
    """

    invalid_facets = []
    valid_facets = []

    for facet in facets:
        if properties_metadata.get_property_metadata_for_str(facet.property_path):
            valid_facets.append(facet)
            continue

        invalid_facets.append(facet)

    result_dict: dict[str, list[FacetOptionDto]] = {}

    if valid_facets:
        with Session(engine) as session:
            try:
                db_query = get_facets_query_builder(
                    properties_metadata
                ).build_facets_data_query(
                    base_query_factory=base_query_factory,
                    entity_id_column=entity_id_column,
                    facets=valid_facets,
                    facet_options_query=facet_options_query,
                )

                db_query_str = str(
                    db_query.compile(
                        dialect=engine.dialect, compile_kwargs={"literal_binds": True}
                    )
                )

                data = session.exec(db_query).all()
            except OperationalError as e:
                raise e  # TODO: TO REMOVE
                logger.warning(
                    f"""Failed to execute query for facet options.
                    Facet options: {json.dumps(facet_options_query.dict())}
                    Error: {e}
                    """
                )
                return {facet.id: [] for facet in facets}

            grouped_by_id_dict = {}

            for facet_data in data:
                if facet_data.facet_id not in grouped_by_id_dict:
                    grouped_by_id_dict[facet_data.facet_id] = []

                # This is to limit the number of options per facet
                # It's done mostly for sqlite, because in sqlite we can't use limit in the subquery
                if (
                    engine.dialect.name == "sqlite"
                    and len(grouped_by_id_dict[facet_data.facet_id])
                    >= OPTIONS_PER_FACET
                ):
                    continue

                grouped_by_id_dict[facet_data.facet_id].append(facet_data)

            for facet in facets:
                facet_cel = facet_options_query.facet_queries.get(facet.id, "")
                facet_key = (
                    facet.property_path
                    + hashlib.sha1(facet_cel.encode("utf-8")).hexdigest()
                )
                property_mapping = properties_metadata.get_property_metadata_for_str(
                    facet.property_path
                )
                result_dict.setdefault(facet.id, [])

                if facet_key in grouped_by_id_dict:
                    result_dict[facet.id] = [
                        FacetOptionDto(
                            display_name=str(facet_value),
                            value=map_facet_option_value(
                                facet_value, property_mapping.data_type
                            ),
                            matches_count=0 if matches_count is None else matches_count,
                        )
                        for facet_id, facet_value, matches_count in grouped_by_id_dict[
                            facet_key
                        ]
                    ]

                if property_mapping is None:
                    result_dict[facet.id] = []
                    continue

                if property_mapping.enum_values:
                    if facet.id in result_dict:
                        values_with_zero_matches = [
                            enum_value
                            for enum_value in property_mapping.enum_values
                            if enum_value
                            not in [
                                facet_option.value
                                for facet_option in result_dict[facet.id]
                            ]
                        ]
                    else:
                        result_dict.setdefault(facet.id, [])
                        values_with_zero_matches = property_mapping.enum_values

                    for enum_value in values_with_zero_matches:
                        result_dict[facet.id].append(
                            FacetOptionDto(
                                display_name=enum_value,
                                value=enum_value,
                                matches_count=0,
                            )
                        )
                    result_dict[facet.id] = sorted(
                        result_dict[facet.id],
                        key=lambda facet_option: (
                            property_mapping.enum_values.index(facet_option.value)
                            if facet_option.value in property_mapping.enum_values
                            else -100  # put unknown values at the end
                        ),
                        reverse=True,
                    )

    for invalid_facet in invalid_facets:
        result_dict[invalid_facet.id] = []

    return result_dict


def create_facet(tenant_id: str, entity_type, facet: CreateFacetDto) -> FacetDto:
    """
    Creates a new facet for a given tenant and returns the created facet's details.
    Args:
        tenant_id (str): The ID of the tenant for whom the facet is being created.
        facet (CreateFacetDto): The data transfer object containing the details of the facet to be created.
    Returns:
        FacetDto: The data transfer object containing the details of the created facet.
    """

    with Session(engine) as session:
        facet_db = Facet(
            id=str(uuid4()),
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
        return FacetDto(
            id=str(facet_db.id),
            property_path=facet_db.property_path,
            name=facet_db.name,
            description=facet_db.description,
            is_static=False,
            is_lazy=True,
            type=facet_db.type,
        )
    return None


def delete_facet(tenant_id: str, entity_type: str, facet_id: str) -> bool:
    """
    Deletes a facet from the database for a given tenant.

    Args:
        tenant_id (str): The ID of the tenant.
        facet_id (str): The ID of the facet to be deleted.

    Returns:
        bool: True if the facet was successfully deleted, False otherwise.
    """
    with Session(engine) as session:
        facet = session.exec(
            select(Facet)
            .where(Facet.tenant_id == tenant_id)
            .where(Facet.id == UUID(facet_id))
            .where(Facet.entity_type == entity_type)
        ).first()[0] # result returned as tuple
        if facet:
            session.delete(facet)
            session.commit()
            return True
        return False


def get_facets(
    tenant_id: str, entity_type: str, facet_ids_to_load: list[str] = None
) -> list[FacetDto]:
    """
    Retrieve a list of facet DTOs for a given tenant and entity type.

    Args:
        tenant_id (str): The ID of the tenant.
        entity_type (str): The type of the entity.
        facet_ids_to_load (list[str], optional): A list of facet IDs to load. Defaults to None.

    Returns:
        list[FacetDto]: A list of FacetDto objects representing the facets.
    """
    with Session(engine) as session:
        query = select(Facet).where(
            Facet.tenant_id == tenant_id,
            Facet.entity_type == entity_type
        )

        if facet_ids_to_load:
            query = query.filter(Facet.id.in_([UUID(id) for id in facet_ids_to_load]))

        facets_from_db = session.exec(query).all()

        facet_dtos = []

        for facet in facets_from_db:
            facet = facet[0] # because each row is returned as a tuple
            facet_dtos.append(
                FacetDto(
                    id=str(facet.id),
                    property_path=facet.property_path,
                    name=facet.name,
                    is_static=False,
                    is_lazy=True,
                    type=FacetType.str,
                )
            )

        return facet_dtos
