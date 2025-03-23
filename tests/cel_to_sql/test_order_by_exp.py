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
    FieldMappingConfiguration("floatNumberColumn", "float_number_column", float),
    FieldMappingConfiguration("intNumberColumn", "int_number_column", int),
    FieldMappingConfiguration(
        map_from_pattern="floatNumberColumnFromJson",
        map_to=["JSON(json_column).*"],
        data_type=float,
    ),
    FieldMappingConfiguration(
        map_from_pattern="intNumberColumnFromJson",
        map_to=["JSON(json_column).*"],
        data_type=int,
    ),
    FieldMappingConfiguration(
        map_from_pattern="intNumberColumnFromMultipleJson",
        map_to=["JSON(json_column_first).*", "JSON(json_column_second).*"],
        data_type=int,
    ),
]
properties_metadata = PropertiesMetadata(fake_field_configurations)
testcases_dict = {}

with open(
    os.path.join(os.path.dirname(__file__), "order-by-exp-test-cases.json"),
    "r",
    encoding="utf-8",
) as file:
    json_dumps = json.load(file)
    flatten_test_cases = []

    for item in json_dumps:
        print(item)
        field_ = item["field"]
        expected_sql_dialect_based: dict = item["expected_sql_dialect_based"]
        description_ = item["description"]

        for dialect_ in ["sqlite", "mysql", "postgresql"]:
            expected_sql_ = expected_sql_dialect_based.get(dialect_, "no_expected_sql")
            dict_key = f"{dialect_}_{description_}"
            testcases_dict[dict_key] = [dialect_, field_, expected_sql_]


@pytest.mark.parametrize("testcase_key", list(testcases_dict.keys()))
def test_order_by_exp(testcase_key):
    dialect_name, field, expected_sql = testcases_dict[testcase_key]

    if expected_sql == "no_expected_sql":
        pytest.fail("No expected order by expression for this dialect")
        pytest.skip("No expected order by expression for this dialect")

    instance = get_cel_to_sql_provider_for_dialect(dialect_name, properties_metadata)
    actual_sql_filter = instance.get_order_by_exp(field)
    assert actual_sql_filter == expected_sql
