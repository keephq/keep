from datetime import datetime
from typing import List
from keep.api.core.cel_to_sql.ast_nodes import ConstantNode
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    SimpleFieldMapping,
)
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider

class CelToMySqlProvider(BaseCelToSqlProvider):
    def json_extract_as_text(self, column: str, path: str) -> str:
        return f"JSON_UNQUOTE({self._json_extract(column, path)})"

    def cast(self, expression_to_cast: str, to_type, force=False):
        if to_type is bool:
            cast_conditions = {
                # f"{expression_to_cast} is NULL": "FALSE",
                f"{expression_to_cast} = 'true'": "TRUE",
                f"{expression_to_cast} = 'false'": "FALSE",
                f"{expression_to_cast} = ''": "FALSE",
                f"CAST({expression_to_cast} AS SIGNED) >= 1": "TRUE",
                f"CAST({expression_to_cast} AS SIGNED) <= 0": "FALSE",
            }
            result = " ".join(
                [f"WHEN {key} THEN {value}" for key, value in cast_conditions.items()]
            )
            result = f"CASE {result} ELSE NULL END"
            return result

        if not force:
            # MySQL does not need explicit cast for other than boolean because it does it implicitly
            # so if not forced, we return the expression as is
            return expression_to_cast

        if to_type is int:
            return f"CAST({expression_to_cast} AS SIGNED)"
        elif to_type is float:
            return f"CAST({expression_to_cast} AS DOUBLE)"
        else:
            return expression_to_cast

    def _json_extract(self, column: str, path: str) -> str:
        return f"JSON_EXTRACT({column}, '$.{path}')"

    def _get_order_by_field(self, field_mapping, data_type: type):
        if isinstance(field_mapping, JsonFieldMapping):
            # just json_extract is used because it correctly sorts by numbers and strings
            return self._json_extract(
                field_mapping.json_prop, field_mapping.prop_in_json
            )
        elif isinstance(field_mapping, SimpleFieldMapping):
            return field_mapping.map_to

        raise ValueError(f"Unsupported field mapping type: {type(field_mapping)}")

    def _visit_constant_node(self, value: str) -> str:
        if isinstance(value, datetime):
            date_str = self.literal_proc(value.strftime("%Y-%m-%d %H:%M:%S"))
            date_exp = f"CAST({date_str} as DATETIME)"
            return date_exp
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"

        return super()._visit_constant_node(value)

    def coalesce(self, args):
        return f"COALESCE({', '.join(args)})"

    def _visit_contains_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.contains accepts 1 argument but got {len(method_args)}')
        value = (
            method_args[0].value.lower()
            if isinstance(method_args[0].value, str)
            else method_args[0].value
        )
        processed_literal = self.literal_proc(value)
        unquoted_literal = processed_literal[1:-1]
        return f"{property_path} IS NOT NULL AND LOWER({property_path}) LIKE '%{unquoted_literal}%'"

    def _visit_starts_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.startsWith accepts 1 argument but got {len(method_args)}')
        value = (
            method_args[0].value.lower()
            if isinstance(method_args[0].value, str)
            else method_args[0].value
        )
        processed_literal = self.literal_proc(value)
        unquoted_literal = processed_literal[1:-1]
        return f"{property_path} IS NOT NULL AND LOWER({property_path}) LIKE '{unquoted_literal}%'"

    def _visit_ends_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.endsWith accepts 1 argument but got {len(method_args)}')
        value = (
            method_args[0].value.lower()
            if isinstance(method_args[0].value, str)
            else method_args[0].value
        )
        processed_literal = self.literal_proc(value)
        unquoted_literal = processed_literal[1:-1]
        return f"{property_path} IS NOT NULL AND LOWER({property_path}) LIKE '%{unquoted_literal}'"
