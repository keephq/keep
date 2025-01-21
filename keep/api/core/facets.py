from sqlalchemy import func, literal, literal_column, select, text
from keep.api.core.cel_to_sql.properties_metadata import JsonMapping, PropertiesMetadata, SimpleMapping
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider_for_dialect,
)
from keep.api.models.facet import CreateFacetDto, FacetDto, FacetOptionDto
from uuid import UUID, uuid4

# from pydantic import BaseModel
from sqlmodel import Session

from keep.api.core.db import engine
from keep.api.models.db.facet import Facet, FacetType


def build_facets_data_query(
    dialect: str,
    base_query,
    facets: list[FacetDto],
    properties_metadata: PropertiesMetadata,
    facets_query: dict[str, str],
):
    """
    Builds a SQL query to extract and count facet data based on the provided parameters.

    Args:
        dialect (str): The SQL dialect to use (e.g., 'postgresql', 'mysql').
        base_query: The base SQLAlchemy query object to build upon.
        facets (list[FacetDto]): A list of facet data transfer objects specifying the facets to be queried.
        properties_metadata (PropertiesMetadata): Metadata about the properties to be used in the query.
        cel (str): A CEL (Common Expression Language) string to filter the base query.

    Returns:
        sqlalchemy.sql.Selectable: A SQLAlchemy selectable object representing the constructed query.
    """
    provider_type = get_cel_to_sql_provider_for_dialect(dialect)
    instance = provider_type(properties_metadata)
    base_query = base_query.cte("base_query_cte")

    # Main Query: JSON Extraction and Counting
    union_queries = []

    for facet in facets:
        metadata = properties_metadata.get_property_metadata(facet.property_path)
        group_by_exp = []

        for item in metadata:
            if isinstance(item, JsonMapping):
                group_by_exp.append(
                    instance.json_extract_as_text(item.json_prop, item.prop_in_json)
                )
            elif isinstance(metadata[0], SimpleMapping):
                group_by_exp.append(item.map_to)
        
        casted = f"{instance.coalesce([instance.cast(item, str) for item in group_by_exp])}"

        union_queries.append(
            select(
                literal(facet.id).label("facet_id"),
                text(f"MIN({casted}) AS facet_value"),
                func.count(func.distinct(literal_column("entity_id"))).label(
                    "matches_count"
                ),
            )
            .select_from(base_query)
            .filter(text(instance.convert_to_sql_str(facets_query[facet.id])))
            .group_by(text(instance.coalesce(group_by_exp) if len(group_by_exp) > 1 else group_by_exp[0]))
        )

    query = None

    if len(union_queries) > 1:
        query = union_queries[0].union_all(*union_queries[1:])
    else:
        query = union_queries[0]

    return query


def get_facet_options(
    base_query,
    facets: list[FacetDto],
    facets_query: dict[str, str],
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

    valid_facets = [facet for facet in facets if properties_metadata.get_property_metadata(facet.property_path)]

    with Session(engine) as session:
        db_query = build_facets_data_query(
            dialect=session.bind.dialect.name,
            base_query=base_query,
            facets=valid_facets,
            properties_metadata=properties_metadata,
            facets_query=facets_query,
        )
        data = session.exec(db_query).all()
        grouped_by_id_dict = {}

        for facet_data in data:
            if facet_data.facet_id not in grouped_by_id_dict:
                grouped_by_id_dict[facet_data.facet_id] = []

            grouped_by_id_dict[facet_data.facet_id].append(facet_data)

        result_dict: dict[str, list[FacetOptionDto]] = {}

        for facet in facets:
            if facet.id in grouped_by_id_dict:
                result_dict[facet.id] = [
                    FacetOptionDto(
                        display_name=str(facet_value),
                        value=facet_value,
                        matches_count=matches_count,
                    )
                    for facet_id, facet_value, matches_count in grouped_by_id_dict[facet.id]
                ]
                continue

            result_dict[facet.id] = []

        return result_dict


def create_facet(tenant_id: str, facet: CreateFacetDto) -> FacetDto:
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
            entity_type="incident",
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


def delete_facet(tenant_id: str, facet_id: str) -> bool:
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
