import fnmatch
import re

class SimpleMapping:
    def __init__(self, map_to: str):
        self.map_to = map_to

class JsonMapping:
    def __init__(self, json_prop: str, prop_in_json: str):
        self.json_prop = json_prop
        self.prop_in_json = prop_in_json

class FieldMappingConfiguration:
    def __init__(self, map_from_pattern: str, map_to: list[str] | str, is_json: bool = False):
        self.map_from_pattern = map_from_pattern
        self.map_to = map_to
        self.is_json = is_json

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

    def get_property_metadata(self, prop_path: str):
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
        
        if field_mapping_config:
            map_to: list[str] = field_mapping_config.map_to if isinstance(field_mapping_config.map_to, list) else [field_mapping_config.map_to]

            if field_mapping_config.is_json:
                prop_in_json = None

                if '*' in mapping_key:
                    regex_pattern = re.escape(mapping_key).replace(r'\*', r'(.*)')
                    regex = re.compile(f"^{regex_pattern}$")
                    match = regex.match(prop_path)
                    prop_in_json = match.group(1)

                return [JsonMapping(item, prop_in_json) for item in map_to]
            
            return [SimpleMapping(item) for item in map_to]
        
        return None
