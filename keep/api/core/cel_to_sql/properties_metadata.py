import fnmatch


class PropertiesMetadata:
    """
    A class to handle metadata for properties, including known fields and wildcard patterns.

    Attributes:
        known_fields_mapping (dict): A dictionary mapping property paths to their metadata.
        known_fields_wildcards (dict): A dictionary of known fields that contain wildcard patterns.

    Methods:
        get_property_metadata(prop_path: str) -> list[str]:
            Retrieves the metadata for a given property path. If the property path is not directly
            found in the known fields mapping, it checks for wildcard patterns.
    """
    def __init__(self, known_fields_mapping: dict):
        self.known_fields_mapping = known_fields_mapping
        self.known_fields_wildcards = {key: known_fields_mapping[key] for key in known_fields_mapping if "*" in key}

    def get_property_mapping(self, prop_path: str) -> list[str]:
        field_mapping = self.get_property_metadata(prop_path)

        if field_mapping:
            if "take_from" in field_mapping:
                result = []
                for take_from in field_mapping.get("take_from"):
                    if field_mapping.get("type") == "json":
                        result.append(f'JSON({take_from}).{prop_path}')
                    elif field_mapping.get("type") == "one_to_one":
                        result.append(f'{take_from}.{prop_path}')
                return result

            if "field" in field_mapping:
                return [field_mapping.get("field")]

        return [prop_path]

    def get_property_metadata(self, prop_path: str) -> dict:
        if prop_path in self.known_fields_mapping:
            return self.known_fields_mapping[prop_path]

        if prop_path in self.known_fields_mapping:
            return self.known_fields_mapping.get(prop_path)

        # If no direct mapping is found, check for wildcard patterns in known fields
        for pattern in self.known_fields_wildcards:
            if fnmatch.fnmatch(prop_path, pattern):
                return self.known_fields_wildcards[pattern]
