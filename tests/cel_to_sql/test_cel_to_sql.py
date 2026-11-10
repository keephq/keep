import json
import os
import sqlite3
from importlib import import_module

import pytest

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    PropertiesMetadata,
)
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider_for_dialect,
)
from keep.api.core.cel_to_sql.sql_providers.mysql import CelToMySqlProvider
from keep.api.core.cel_to_sql.sql_providers.postgresql import CelToPostgreSqlProvider

fake_field_configurations = [
    FieldMappingConfiguration(
        map_from_pattern="id", map_to=["entityId"], data_type=DataType.UUID
    ),
    FieldMappingConfiguration(
        map_from_pattern="name",
        map_to=["user_generated_name", "ai_generated_name"],
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="summary", map_to=["user_summary", "generated_summary"]
    ),
    FieldMappingConfiguration(map_from_pattern="created_at", map_to="created_at"),
    FieldMappingConfiguration(
        map_from_pattern="severity",
        map_to="severity",
        enum_values=["info", "low", "medium", "high", "critical"],
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="alert.provider_type",
        map_to="incident_alert_provider_type",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="jsonArray",
        map_to="entity.jsonArray",
        data_type=DataType.ARRAY,
    ),
    FieldMappingConfiguration(
        map_from_pattern="created_at",
        map_to="created_at",
        data_type=DataType.DATETIME,
    ),
    FieldMappingConfiguration(
        map_from_pattern="propWithUnknownType",
        map_to="columnWithUnknownType",
    ),
    FieldMappingConfiguration(
        map_from_pattern="booleanFromJson",
        map_to=["JSON(alert_event).*"],
        data_type=DataType.BOOLEAN,
    ),
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


@pytest.mark.parametrize(
    "key",
    ["x') OR (1=1) OR ('", 'with "double" quotes', r"back\slash", "cpu%"],
)
def test_json_index_key_is_escaped_on_sqlite(key):
    """A JSON key with quotes or a backslash matches only the rows holding that key."""
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE alerts (alert_enrichments TEXT, alert_event TEXT)")
    db.executemany(
        "INSERT INTO alerts VALUES (?, ?)",
        [
            ("{}", json.dumps({"labels": {key: "v"}})),
            ("{}", json.dumps({"labels": {"other": "v"}})),
        ],
    )
    instance = get_cel_to_sql_provider_for_dialect("sqlite", properties_metadata)
    # CEL string literals here only unescape quotes, so escape just the double quotes.
    cel_key = '"' + key.replace('"', '\\"') + '"'

    try:
        for cel in (
            f"alert.labels[{cel_key}] == 'v'",
            f"has(alert.labels[{cel_key}])",
        ):
            sql = instance.convert_to_sql_str(cel)
            matched = db.execute(f"SELECT count(*) FROM alerts WHERE {sql}").fetchone()[0]
            assert matched == 1, sql
    finally:
        db.close()


@pytest.mark.parametrize("dialect_name", ["postgresql", "mysql"])
def test_json_index_key_is_quoted_for_the_real_dialect(dialect_name):
    """Keys with %, quotes and backslashes are quoted once for the dialect that runs them."""
    dialect = import_module(f"sqlalchemy.dialects.{dialect_name}").dialect()
    provider_cls = {
        "postgresql": CelToPostgreSqlProvider,
        "mysql": CelToMySqlProvider,
    }[dialect_name]
    instance = provider_cls(dialect, properties_metadata)

    sql = instance.convert_to_sql_str("alert.labels[\"cpu%\"] == 'v'")
    assert "cpu%'" in sql or 'cpu%"' in sql
    assert "%%" not in sql

    sql = instance.convert_to_sql_str("alert.labels[\"x') OR (1=1) OR ('\"] == 'v'")
    assert "x'') OR (1=1) OR (''" in sql

    sql = instance.convert_to_sql_str('has(alert.labels["a\\"b"])')
    expected_key = '"a\\\\"b"' if dialect_name == "mysql" else '"a\\"b"'
    assert expected_key in sql, sql


def test_mysql_json_path_keeps_backslashes_without_backslash_escapes():
    """With NO_BACKSLASH_ESCAPES, MySQL keys keep single backslashes in the path."""
    dialect = import_module("sqlalchemy.dialects.mysql").dialect()
    dialect._backslash_escapes = False
    instance = CelToMySqlProvider(dialect, properties_metadata)

    sql = instance.convert_to_sql_str('has(alert.labels["a\\"b"])')
    assert '"a\\"b"' in sql, sql
