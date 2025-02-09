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
        field_mappings: list[SimpleFieldMapping | JsonFieldMapping],
        enum_values: list[str],
    ):
        self.field_mappings = field_mappings
        self.enum_values = enum_values


class FieldMappingConfiguration:

    def __init__(
        self,
        map_from_pattern: str,
        map_to: list[str] | str,
        enum_values: list[str] = None,
    ):
        self.map_from_pattern = map_from_pattern
        self.enum_values = enum_values
        self.map_to = map_to


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
            return PropertyMetadataInfo(
                field_mappings=[SimpleFieldMapping(prop_path)],
                enum_values=None,
            )

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
            splitted = item.split(".")
            match = re.match(r"JSON\(([^)]+)\).*", splitted[0])

            # If first element is a JSON mapping (JSON(event).tagsContainer.*)
            # we extract JSON column (event) and replace * with prop_in_json
            if match:
                prop_in_json_list = [spl for spl in splitted]
                if "*" in splitted:
                    prop_in_json_list[splitted.index("*")] = template_prop
                else:
                    prop_in_json_list.append(template_prop)

                json_prop = match.group(1)
                field_mappings.append(
                    JsonFieldMapping(
                        json_prop=json_prop,
                        prop_in_json=".".join(
                            prop_in_json_list[1:]
                        ),  # skip JSON column and take the rest
                    )
                )
                continue

            field_mappings.append(SimpleFieldMapping(item))

        return PropertyMetadataInfo(
            field_mappings=field_mappings,
            enum_values=field_mapping_config.enum_values,
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
