from datetime import datetime
from typing import List
from uuid import UUID
from keep.api.core.cel_to_sql.ast_nodes import ConstantNode
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    SimpleFieldMapping,
)
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider
from keep.api.core.cel_to_sql.ast_nodes import DataType

class CelToPostgreSqlProvider(BaseCelToSqlProvider):

    def json_extract_as_text(self, column: str, path: list[str]) -> str:
        all_columns = [column] + [f"'{item}'" for item in path]

        json_property_path = " -> ".join(all_columns[:-1])
        return f"({json_property_path}) ->> {all_columns[-1]}"  # (json_column -> 'labels' -> tags) ->> 'service'

    def cast(self, expression_to_cast: str, to_type: DataType, force=False):
        if to_type == DataType.STRING:
            to_type_str = "TEXT"
        elif to_type == DataType.INTEGER or to_type == DataType.FLOAT:
            to_type_str = "FLOAT"
        elif to_type == DataType.NULL:
            return expression_to_cast
        elif to_type == DataType.DATETIME:
            to_type_str = "TIMESTAMP"
        elif to_type == DataType.BOOLEAN:
            to_type_str = "BOOLEAN"
        else:
            raise ValueError(f"Unsupported type: {type}")

        return f"({expression_to_cast})::{to_type_str}"

    def get_field_expression(self, cel_field):
        """
        Overriden, because for PostgreSql we need to cast columns to known data types (because every JSON operation returns just text).
        This is used in ordering to correctly order rows in accordance to their types and not lexicographically.
        """
        metadata = self.properties_metadata.get_property_metadata_for_str(cel_field)
        field_expressions = []

        for field_mapping in metadata.field_mappings:
            if isinstance(field_mapping, JsonFieldMapping):
                json_exp = self.json_extract_as_text(
                    field_mapping.json_prop, field_mapping.prop_in_json
                )

                if (
                    metadata.data_type != DataType.STRING
                    and metadata.data_type is not None
                ):
                    json_exp = self.cast(json_exp, metadata.data_type)
                field_expressions.append(json_exp)
                continue
            elif isinstance(field_mapping, SimpleFieldMapping):
                field_expressions.append(field_mapping.map_to)
                continue

            raise ValueError(f"Unsupported field mapping type: {type(field_mapping)}")

        if len(field_expressions) > 1:
            return self.coalesce(field_expressions)
        else:
            return field_expressions[0]

    def _visit_constant_node(
        self, value: str, expected_data_type: DataType = None
    ) -> str:
        if expected_data_type == DataType.UUID:
            str_value = str(value)
            try:
                # Because PostgreSQL works with UUID with dashes, we need to convert it to a UUID with dashes string
                # Example: 123e4567e89b12d3a456426614174000 -> 123e4567-e89b-12d3-a456-426614174000
                # Example2: 123e4567-e89b-12d3-a456-426614174000 -> 123e4567-e89b-12d3-a456-426614174000 (dashed UUID in CEL is also supported)
                value = str(UUID(str_value))
            except ValueError:
                pass

        if isinstance(value, datetime):
            date_str = self.literal_proc(value.strftime("%Y-%m-%d %H:%M:%S"))
            date_exp = f"CAST({date_str} as TIMESTAMP)"
            return date_exp

        return super()._visit_constant_node(value)

    def _visit_contains_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.contains accepts 1 argument but got {len(method_args)}')

        processed_literal = self.literal_proc(method_args[0].value)
        unquoted_literal = processed_literal[1:-1]
        return f"{property_path} IS NOT NULL AND {property_path} ILIKE '%{unquoted_literal}%'"

    def _visit_starts_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.startsWith accepts 1 argument but got {len(method_args)}')
        processed_literal = self.literal_proc(method_args[0].value)
        unquoted_literal = processed_literal[1:-1]
        return f"{property_path} IS NOT NULL AND {property_path} ILIKE '{unquoted_literal}%'"

    def _visit_ends_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.endsWith accepts 1 argument but got {len(method_args)}')
        processed_literal = self.literal_proc(method_args[0].value)
        unquoted_literal = processed_literal[1:-1]
        return f"{property_path} IS NOT NULL AND {property_path} ILIKE '%{unquoted_literal}'"
