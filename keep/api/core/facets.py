import json
import logging
from sqlalchemy import Column, String, cast, func, literal, literal_column, select, text
from sqlalchemy.exc import OperationalError
from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    JsonFieldMapping,
    PropertiesMetadata,
    SimpleFieldMapping,
)
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider,
)
from keep.api.models.facet import CreateFacetDto, FacetDto, FacetOptionDto, FacetOptionsQueryDto
from uuid import UUID, uuid4

# from pydantic import BaseModel
from sqlmodel import Session

from keep.api.core.db import engine
from keep.api.models.db.facet import Facet, FacetType
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger(__name__)

OPTIONS_PER_FACET = 50


def build_facet_selects(properties_metadata, facets):
    cel_to_sql_instance = get_cel_to_sql_provider(properties_metadata)
    new_fields_config: list[FieldMappingConfiguration] = []
    select_expressions = {}

    for facet in facets:
        property_metadata = properties_metadata.get_property_metadata_for_str(
            facet.property_path
        )
        if property_metadata is None:
            continue

        select_field = ("facet_" + facet.property_path.replace(".", "_")).lower()

        new_fields_config.append(
            FieldMappingConfiguration(
                map_from_pattern=facet.property_path,
                map_to=[select_field],
                data_type=property_metadata.data_type,
            )
        )
        coalla = []

        for field_mapping in property_metadata.field_mappings:
            if isinstance(field_mapping, JsonFieldMapping):
                coalla.append(
                    cel_to_sql_instance.json_extract_as_text(
                        field_mapping.json_prop, field_mapping.prop_in_json
                    )
                )
            elif isinstance(field_mapping, SimpleFieldMapping):
                coalla.append(field_mapping.map_to)

        select_expressions[select_field] = literal_column(
            cel_to_sql_instance.coalesce(coalla) if len(coalla) > 1 else coalla[0]
        ).label(select_field)

    return {
        "new_fields_config": new_fields_config,
        "select_expressions": list(select_expressions.values()),
    }


def build_facet_subquery_for_column(
    base_query,
    column_name: str,
):
    return select(
        func.distinct(literal_column("entity_id")),
        literal_column(column_name).label("facet_value"),
    ).select_from(base_query)


def build_facet_subquery_for_json_array(
    base_query,
    column_name: str,
):
    json_table_join = None

    if engine.dialect.name == "sqlite":
        json_table_join = func.json_each(literal_column(column_name)).table_valued(
            "value"
        )
    elif engine.dialect.name == "postgresql":
        json_table_join = func.jsonb_array_elements_text(
            cast(literal_column(column_name), JSONB)
        ).table_valued("value")
    elif engine.dialect.name == "mysql":
        # MySQL throws errors due to JSON_TABLE without LIMIT
        base_query = base_query.limit(1_000_000).cte(f"{column_name}_base_query")
        json_table_join = func.json_table(
            literal_column(column_name), Column("value", String(127))
        ).table_valued("value")

    return select(
        func.distinct(base_query.c.entity_id),
        json_table_join.c.value.label("facet_value"),
    ).select_from(base_query, json_table_join)


def build_facets_data_query(
    base_query,
    facets: list[FacetDto],
    properties_metadata: PropertiesMetadata,
    facet_options_query: FacetOptionsQueryDto,
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
    instance = get_cel_to_sql_provider(properties_metadata)

    if facet_options_query.cel:
        base_query = base_query.filter(
            text(instance.convert_to_sql_str(facet_options_query.cel))
        )

    # Main Query: JSON Extraction and Counting
    union_queries = []
    facet_selects_metadata = build_facet_selects(properties_metadata, facets)
    new_fields_config = facet_selects_metadata["new_fields_config"]
    facets_properties_metadata = PropertiesMetadata(new_fields_config)
    facets_cel_to_sql_instance = get_cel_to_sql_provider(facets_properties_metadata)

    base_query_common = base_query.cte("base_query")

    for facet in facets:
        metadata = facets_properties_metadata.get_property_metadata_for_str(
            facet.property_path
        )
        facet_value = []

        for item in metadata.field_mappings:
            if isinstance(item, JsonFieldMapping):
                facet_value.append(
                    facets_cel_to_sql_instance.json_extract_as_text(
                        item.json_prop, item.prop_in_json
                    )
                )
            elif isinstance(metadata.field_mappings[0], SimpleFieldMapping):
                facet_value.append(item.map_to)

        column_name = f"{facets_cel_to_sql_instance.coalesce([facets_cel_to_sql_instance.cast(item, DataType.STRING) for item in facet_value])}"
        facet_source_subquery = None
        if metadata.data_type == DataType.ARRAY:
            facet_source_subquery = build_facet_subquery_for_json_array(
                base_query,
                column_name,
            )
        else:
            facet_source_subquery = build_facet_subquery_for_column(
                base_query_common,
                column_name,
            )

        facet_source_subquery = facet_source_subquery.filter(
            text(
                facets_cel_to_sql_instance.convert_to_sql_str(
                    facet_options_query.facet_queries[facet.id]
                )
            )
        )

        facet_sub_query = (
            select(
                literal(facet.id).label("facet_id"),
                literal_column("facet_value"),
                func.count().label("matches_count"),
            )
            .select_from(facet_source_subquery)
            .group_by(literal_column("facet_id"), literal_column("facet_value"))
        )

        # For SQLite we can't limit the subquery
        # so we limit the result after the result is fetched in get_facet_options
        if engine.dialect.name != "sqlite":
            facet_sub_query = facet_sub_query.limit(OPTIONS_PER_FACET)

        union_queries.append(facet_sub_query)

    query = None

    if len(union_queries) > 1:
        query = union_queries[0].union_all(*union_queries[1:])
    else:
        query = union_queries[0]

    return query


def get_facet_options(
    base_query,
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
                db_query = build_facets_data_query(
                    base_query=base_query,
                    facets=valid_facets,
                    properties_metadata=properties_metadata,
                    facet_options_query=facet_options_query,
                )

                data = session.exec(db_query).all()
            except OperationalError as e:
                raise e  # TODO: REMOVE IT
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
                property_mapping = properties_metadata.get_property_metadata_for_str(
                    facet.property_path
                )
                result_dict.setdefault(facet.id, [])

                if facet.id in grouped_by_id_dict:
                    result_dict[facet.id] = [
                        FacetOptionDto(
                            display_name=str(facet_value),
                            value=facet_value,
                            matches_count=matches_count,
                        )
                        for facet_id, facet_value, matches_count in grouped_by_id_dict[
                            facet.id
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
