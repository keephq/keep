from __future__ import annotations

import fnmatch
import re
from typing import Optional, Union, List, Dict, Tuple

from keep.api.core.cel_to_sql.ast_nodes import DataType


class SimpleFieldMapping:
    def __init__(self, map_to: str):
        self.map_to = map_to


class JsonFieldMapping:
    def __init__(self, json_prop: str, prop_in_json: list[str]):
        self.json_prop = json_prop
        self.prop_in_json = prop_in_json


class PropertyMetadataInfo:
    def __init__(
        self,
        field_name: str,
        field_mappings: list[Union[SimpleFieldMapping, JsonFieldMapping]],
        enum_values: Optional[list[str]] = None,
        data_type: Optional[DataType] = None,
    ):
        self.field_name = field_name
        self.field_mappings = field_mappings
        self.enum_values = enum_values
        self.data_type = data_type


class FieldMappingConfiguration:
    def __init__(
        self,
        map_from_pattern: str,
        map_to: Union[list[str], str],
        data_type: Optional[DataType] = None,
        enum_values: Optional[list[str]] = None,
    ):
        self.map_from_pattern = map_from_pattern
        self.enum_values = enum_values
        self.data_type = data_type
        self.map_to: list[str] = map_to if isinstance(map_to, list) else [map_to]


def remap_fields_configurations(
    mapping_rules: dict[str, str],
    field_configurations: list[FieldMappingConfiguration],
) -> list[FieldMappingConfiguration]:
    # Copy configurations (shallow copy of values, not shared objects)
    result: list[FieldMappingConfiguration] = [
        FieldMappingConfiguration(
            map_from_pattern=item.map_from_pattern,
            map_to=list(item.map_to),
            enum_values=item.enum_values,
            data_type=item.data_type,
        )
        for item in field_configurations
    ]

    for src, dst in mapping_rules.items():
        for cfg in result:
            cfg.map_to = [t.replace(src, dst) for t in cfg.map_to]

    return result


class PropertiesMetadata:
    """
    Maps CEL property paths to one or more DB field mappings.
    Supports:
      - direct mappings
      - wildcard patterns (fnmatch)
      - JSON mappings in the form JSON(column).path.*
    """

    _json_prefix_re = re.compile(r"^JSON\(([^)]+)\)(?:\.(.*))?$")

    def __init__(self, fields_mapping_configurations: list[FieldMappingConfiguration]):
        self.wildcard_configurations: dict[str, FieldMappingConfiguration] = {}
        self.known_configurations: dict[str, FieldMappingConfiguration] = {}

        for cfg in fields_mapping_configurations:
            normalized_from = self.__get_property_path_str(
                self.__extract_fields(cfg.map_from_pattern)
            )
            normalized_cfg = FieldMappingConfiguration(
                map_from_pattern=normalized_from,
                map_to=list(cfg.map_to),
                data_type=cfg.data_type,
                enum_values=cfg.enum_values,
            )

            if "*" in cfg.map_from_pattern:
                self.wildcard_configurations[normalized_from] = normalized_cfg
            else:
                self.known_configurations[normalized_from] = normalized_cfg

    def get_property_metadata_for_str(self, prop_path_str: str) -> Optional[PropertyMetadataInfo]:
        return self.get_property_metadata(self.__extract_fields(prop_path_str))

    def get_property_metadata(self, prop_path: list[str]) -> Optional[PropertyMetadataInfo]:
        prop_path_str = self.__get_property_path_str(prop_path)
        cfg, mapping_key = self.__find_mapping_configuration(prop_path_str)

        if not cfg:
            return None

        # Determine wildcard captured value (single '*' support)
        wildcard_value: Optional[str] = None
        if "*" in mapping_key:
            wildcard_value = self.__extract_wildcard_value(mapping_key, prop_path_str)

        field_mappings: list[Union[SimpleFieldMapping, JsonFieldMapping]] = []
        for target in cfg.map_to:
            json_match = self._json_prefix_re.match(target)
            if json_match:
                json_col = json_match.group(1)
                json_path_str = json_match.group(2) or ""   # everything after JSON(col).

                json_tokens = self.__extract_fields(json_path_str) if json_path_str else []

                # Replace '*' token if present, else append wildcard_value if we have one
                if "*" in json_tokens and wildcard_value is not None:
                    json_tokens = [wildcard_value if t == "*" else t for t in json_tokens]
                elif wildcard_value is not None:
                    # If mapping is like JSON(event).labels (no '*'), treat wildcard as leaf
                    json_tokens.append(wildcard_value)

                # If no wildcard in mapping key, use full prop path string as a leaf only if mapping uses '*'
                # (keeps behavior sane and avoids injecting full CEL path into JSON unless explicitly asked)
                if "*" not in mapping_key and "*" in target:
                    # Example: mapping_key = alert.labels, target = JSON(event).labels.*
                    # Use the last segment of prop_path as leaf
                    json_tokens = [t if t != "*" else prop_path[-1] for t in json_tokens]

                field_mappings.append(JsonFieldMapping(json_prop=json_col, prop_in_json=json_tokens))
            else:
                field_mappings.append(SimpleFieldMapping(target))

        return PropertyMetadataInfo(
            field_name=prop_path_str,
            field_mappings=field_mappings,
            enum_values=cfg.enum_values,
            data_type=cfg.data_type,
        )

    def __extract_wildcard_value(self, pattern: str, value: str) -> Optional[str]:
        # Convert fnmatch-style pattern to safe regex capture for single '*'
        # Use non-greedy capture so it doesn’t swallow everything.
        regex_pattern = re.escape(pattern).replace(r"\*", r"(.*?)")
        m = re.match(f"^{regex_pattern}$", value)
        if not m:
            return None
        return m.group(1)

    def __extract_fields(self, property_path_str: str) -> list[str]:
        """
        Extracts tokens from:
          a.b.c
          a[b].c
          a.[weird.key].c
        """
        if property_path_str is None or property_path_str == "":
            return []
        pattern = re.compile(r"\[([^\[\]]+)\]|([^.]+)")
        matches = pattern.findall(property_path_str)
        return [m[0] or m[1] for m in matches if (m[0] or m[1])]

    def __get_property_path_str(self, prop_path: list[str]) -> str:
        result = []
        for item in prop_path:
            if re.search(r"[^a-zA-Z0-9*]", item):
                result.append(f"[{item}]")
            else:
                result.append(item)
        return ".".join(result)

    def __find_mapping_configuration(self, prop_path_str: str) -> tuple[Optional[FieldMappingConfiguration], Optional[str]]:
        if prop_path_str in self.known_configurations:
            return self.known_configurations[prop_path_str], prop_path_str

        for pattern, cfg in self.wildcard_configurations.items():
            if fnmatch.fnmatch(prop_path_str, pattern):
                return cfg, pattern

        return None, None