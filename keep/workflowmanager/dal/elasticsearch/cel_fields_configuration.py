from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    PropertiesMetadata,
)


workflow_field_configurations = [
    FieldMappingConfiguration(
        map_from_pattern="name",
        map_to="name",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="description",
        map_to="description",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="started", map_to="started", data_type=DataType.DATETIME
    ),
    FieldMappingConfiguration(
        map_from_pattern="last_execution_status",
        map_to="status",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="last_execution_time",
        map_to="execution_time",
        data_type=DataType.DATETIME,
    ),
    FieldMappingConfiguration(
        map_from_pattern="disabled",
        map_to="is_disabled",
        data_type=DataType.BOOLEAN,
    ),
    FieldMappingConfiguration(
        map_from_pattern="last_updated",
        map_to="last_updated",
        data_type=DataType.DATETIME,
    ),
    FieldMappingConfiguration(
        map_from_pattern="created_at",
        map_to="creation_time",
        data_type=DataType.DATETIME,
    ),
    FieldMappingConfiguration(
        map_from_pattern="created_by",
        map_to="created_by",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="updated_by",
        map_to="updated_by",
        data_type=DataType.STRING,
    ),
]


properties_metadata = PropertiesMetadata(workflow_field_configurations)
