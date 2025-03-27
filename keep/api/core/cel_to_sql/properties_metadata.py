import fnmatch
import re


class SimpleFieldMapping:
    def __init__(self, map_to: str):
        self.map_to = map_to


class JsonFieldMapping:

    def __init__(self, json_prop: str, prop_in_json: str):
        self.json_prop = json_prop
        self.prop_in_json = prop_in_json


class PropertyMetadataInfo:

    def __init__(
        self,
        field_name: str,
        field_mappings: list[SimpleFieldMapping | JsonFieldMapping],
        enum_values: list[str],
        data_type: type = None,
    ):
        self.field_name = field_name
        self.field_mappings = field_mappings
        self.enum_values = enum_values
        self.data_type = data_type


class FieldMappingConfiguration:

    def __init__(
        self,
        map_from_pattern: str,
        map_to: list[str] | str,
        data_type: type = None,
        enum_values: list[str] = None,
    ):
        self.map_from_pattern = map_from_pattern
        self.enum_values = enum_values
        self.data_type = data_type
        self.map_to: list[str] = map_to if isinstance(map_to, list) else [map_to]


def remap_fields_configurations(
    mapping_rules: dict[str, str], field_configurations: list[FieldMappingConfiguration]
) -> list[FieldMappingConfiguration]:
    """
    Remaps the 'map_to' fields in the given field configurations based on the provided mapping rules.

    Args:
        mapping_rules (dict[str, str]): A dictionary where keys are the patterns to be replaced and values are the new patterns.
        field_configurations (list[FieldMappingConfiguration]): A list of FieldMappingConfiguration objects to be remapped.

    Returns:
        list[FieldMappingConfiguration]: A new list of FieldMappingConfiguration objects with updated 'map_to' fields.
    """
    result: list[FieldMappingConfiguration] = [
        FieldMappingConfiguration(
            map_from_pattern=item.map_from_pattern,
            map_to=item.map_to,
            enum_values=item.enum_values,
            data_type=item.data_type,
        )
        for item in field_configurations
    ]

    for map_from, map_to in mapping_rules.items():
        for field_config in result:
            field_config.map_to = [
                item.replace(map_from, map_to) for item in field_config.map_to
            ]

    return result


class PropertiesMetadata:
    """
    A class to handle metadata properties and mappings for given property paths.
    Attributes:
        known_fields_mapping (dict): A dictionary containing known field mappings.
        known_fields_wildcards (dict): A dictionary containing wildcard patterns from known field mappings.
    Methods:
        __init__(known_fields_mapping: dict):
            Initializes the PropertiesMetadata with known field mappings.
        get_property_metadata(prop_path: str):
            Retrieves the metadata for a given property path.
            If the property path matches a known field or a wildcard pattern, it returns the corresponding mappings.
            Supports JSON type mappings and simple field mappings.
    """
    def __init__(self, fields_mapping_configurations: list[FieldMappingConfiguration]):
        self.wildcard_configurations: dict[FieldMappingConfiguration] = {}
        self.known_configurations: dict[FieldMappingConfiguration] = {}
        for field_mapping in fields_mapping_configurations:
            if '*' in field_mapping.map_from_pattern:
                self.wildcard_configurations[field_mapping.map_from_pattern] = field_mapping
                continue

            self.known_configurations[field_mapping.map_from_pattern] = field_mapping

    def get_property_metadata(self, prop_path: str) -> PropertyMetadataInfo:
        field_mapping_config, mapping_key = self.__find_mapping_configuration(prop_path)

        if not field_mapping_config:
            return None

        field_mappings = []

        map_to: list[str] = (
            field_mapping_config.map_to
            if isinstance(field_mapping_config.map_to, list)
            else [field_mapping_config.map_to]
        )
        template_prop = None

        if "*" in mapping_key:
            # if mapping_key is a wildcard pattern (alert.*), extract the template prop (alert)
            regex_pattern = re.escape(mapping_key).replace(r"\*", r"(.*)")
            regex = re.compile(f"^{regex_pattern}$")
            match = regex.match(prop_path)
            template_prop = match.group(1)
        else:
            # otherwise, the template prop is the prop_path itself
            template_prop = prop_path

        for item in map_to:
            match = re.match(r"JSON\(([^)]+)\)", item)

            # If first element is a JSON mapping (JSON(event).tagsContainer.*)
            # we extract JSON column (event) and replace * with prop_in_json
            if match:
                json_prop = match.group(1)
                splitted = item.replace(f"JSON({json_prop})", "").split(".")
                prop_in_json_list = [spl for spl in splitted]
                if "*" in splitted:
                    prop_in_json_list[splitted.index("*")] = template_prop
                else:
                    prop_in_json_list.append(template_prop)

                field_mappings.append(
                    JsonFieldMapping(
                        json_prop=json_prop,
                        prop_in_json=".".join(
                            prop_in_json_list[1:]
                        ),  # skip JSON column and take the rest
                    )
                )
                continue

            splitted = item.split(".")
            field_mappings.append(SimpleFieldMapping(item))

        return PropertyMetadataInfo(
            field_name=prop_path,
            field_mappings=field_mappings,
            enum_values=field_mapping_config.enum_values,
            data_type=field_mapping_config.data_type,
        )

    def __find_mapping_configuration(self, prop_path: str):
        """
        Find the mapping configuration for a given property path.

        This method searches for a direct mapping configuration in the known configurations.
        If no direct mapping is found, it checks for wildcard patterns in the wildcard configurations.

        Args:
            prop_path (str): The property path to find the mapping configuration for.

        Returns:
            tuple: A tuple containing the FieldMappingConfiguration and the mapping key.
                   If no configuration is found, both elements of the tuple will be None.
        """
        field_mapping_config: FieldMappingConfiguration = None
        mapping_key = None

        if prop_path in self.known_configurations:
            field_mapping_config = self.known_configurations[prop_path]
            mapping_key = prop_path

        # If no direct mapping is found, check for wildcard patterns in known fields
        if not field_mapping_config:
            for pattern, field_mapping_config_from_dict in self.wildcard_configurations.items():
                if fnmatch.fnmatch(prop_path, pattern):
                    field_mapping_config = field_mapping_config_from_dict
                    mapping_key = pattern
                    break

        return field_mapping_config, mapping_key
