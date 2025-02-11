import json
import os
import pytest

from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    PropertiesMetadata,
)
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider_for_dialect,
)

fake_field_configurations = [
    FieldMappingConfiguration("name", ["user_generated_name", "ai_generated_name"]),
    FieldMappingConfiguration("summary", ["user_summary", "generated_summary"]),
    FieldMappingConfiguration("created_at", "created_at"),
    FieldMappingConfiguration(
        "severity", "severity", ["info", "low", "medium", "high", "critical"]
    ),
    FieldMappingConfiguration("alert.provider_type", "incident_alert_provider_type"),
    FieldMappingConfiguration(
        map_from_pattern="alert.tags.*",
        map_to=["JSON(alert_event).tagsContainer.*"],
    ),
    FieldMappingConfiguration(
        map_from_pattern="alert.*",
        map_to=["JSON(alert_enrichments).*", "JSON(alert_event).*"],
    ),
]
properties_metadata = PropertiesMetadata(fake_field_configurations)
testcases_dict = {}

with open(
    os.path.join(os.path.dirname(__file__), "cel-to-sql-test-cases.json"),
    "r",
    encoding="utf-8",
) as file:
    json_dumps = json.load(file)
    flatten_test_cases = []

    for item in json_dumps:
        print(item)
        input_cel_ = item["input_cel"]
        expected_sql_dialect_based: dict = item["expected_sql_dialect_based"]
        description_ = item["description"]

        for dialect_ in ['sqlite', 'mysql', 'postgresql']:
            expected_sql_ = expected_sql_dialect_based.get(dialect_, 'no_expected_sql')
            dict_key = f"{dialect_}_{description_}"
            testcases_dict[dict_key] = [dialect_, input_cel_, expected_sql_]


@pytest.mark.parametrize("testcase_key", list(testcases_dict.keys()))
def test_cel_to_sql(testcase_key):
    dialect_name, input_cel, expected_sql = testcases_dict[testcase_key]

    if expected_sql == 'no_expected_sql':
        pytest.fail("No expected SQL for this dialect")
        pytest.skip("No expected SQL for this dialect")

    instance = get_cel_to_sql_provider_for_dialect(dialect_name, properties_metadata)
    actual_sql_filter = instance.convert_to_sql_str(input_cel)
    assert actual_sql_filter == expected_sql
