import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from keep.api.models.db.mapping import MappingRule


class MappingRuleMatcher:
    """
    Class for matching mapping rules using SQL queries instead of in-memory iteration.
    """

    def __init__(
        self, dialect_name: Optional[str] = None, session: Optional[Session] = None
    ):
        """
        Initialize the matcher with the database dialect and session.

        Args:
            dialect_name: Database dialect name
            session: SQLAlchemy session
        """
        self.logger = logging.getLogger(__name__)
        self.dialect_name = dialect_name
        self.session = session

    def get_matching_row(
        self, rule: MappingRule, alert_values: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get the first matching row for a rule using SQL directly on the MappingRule.rows field.

        Args:
            rule: MappingRule to check
            alert_values: Dict of alert attribute values

        Returns:
            First matching row as a dict if found, None otherwise
        """
        if not rule.rows or not alert_values:
            return None

        conditions = []
        params = {}

        params["rule_id"] = rule.id

        # Build the query based on the dialect
        if self.dialect_name == "postgresql":
            # Build SQL conditions from matchers
            for i, and_group in enumerate(rule.matchers):
                and_conditions = []

                for j, attr in enumerate(and_group):
                    attr_value = alert_values.get(attr)
                    if attr_value is not None:
                        param_name = f"val_{i}_{j}"

                        # Handle different value types
                        if isinstance(attr_value, str):
                            # String comparison with wildcard support
                            and_conditions.append(
                                f"(rows->>'{attr}' = :{param_name} OR rows->>'{attr}' = '*')"
                            )
                            params[param_name] = attr_value
                        elif isinstance(attr_value, (int, float, bool)):
                            # For numeric or boolean values
                            and_conditions.append(
                                f"(rows->>'{attr}' = :{param_name} OR rows->>'{attr}' = '*')"
                            )
                            params[param_name] = str(
                                attr_value
                            )  # Convert to string for JSON text comparison
                        else:
                            # For complex types, convert to JSON string
                            and_conditions.append(
                                f"(rows->>'{attr}' = :{param_name} OR rows->>'{attr}' = '*')"
                            )
                            params[param_name] = json.dumps(attr_value)

                if and_conditions:
                    conditions.append(f"({' AND '.join(and_conditions)})")

            if not conditions:
                return None
            # PostgreSQL version
            query = f"""
            SELECT rows::jsonb
            FROM (
                SELECT jsonb_array_elements(rows::jsonb) AS rows
                FROM mappingrule
                WHERE id = :rule_id
            ) AS expanded_rows
            WHERE {' OR '.join(conditions)}
            LIMIT 1
            """
        elif self.dialect_name == "mysql":
            # MySQL version with proper JSON_TABLE syntax
            mysql_conditions = []

            for i, and_group in enumerate(rule.matchers):
                and_conditions = []

                for j, attr in enumerate(and_group):
                    attr_value = alert_values.get(attr)
                    if attr_value is not None:
                        param_name = f"val_{i}_{j}"

                        # Build condition using JSON_EXTRACT for MySQL
                        # Handle the @@ syntax by replacing with . and wrapping in quotes
                        json_attr = attr
                        if "@@" in json_attr:
                            json_attr = json_attr.replace("@@", ".")
                            json_attr = f'"{json_attr}"'
                        else:
                            json_attr = json_attr

                        if isinstance(attr_value, str):
                            and_conditions.append(
                                f"""(JSON_EXTRACT(jt.json_object, '$.{json_attr}') = :{param_name}
                                OR JSON_EXTRACT(jt.json_object, '$.{json_attr}') = '"*"')"""
                            )
                        elif isinstance(attr_value, (int, float)):
                            and_conditions.append(
                                f"""(CAST(JSON_EXTRACT(jt.json_object, '$.{json_attr}') AS CHAR) = :{param_name}
                                OR JSON_EXTRACT(jt.json_object, '$.{json_attr}') = '"*"')"""
                            )
                        else:
                            and_conditions.append(
                                f"""(JSON_EXTRACT(jt.json_object, '$.{json_attr}') = :{param_name}
                                OR JSON_EXTRACT(jt.json_object, '$.{json_attr}') = '"*"')"""
                            )

                if and_conditions:
                    mysql_conditions.append(f"({' AND '.join(and_conditions)})")

            query = f"""
            SELECT jt.json_object
            FROM mappingrule,
            JSON_TABLE(
                mappingrule.rows,
                '$[*]' COLUMNS (
                    sequence_number FOR ORDINALITY,
                    json_object JSON PATH '$'
                )
            ) AS jt
            WHERE mappingrule.id = :rule_id
            AND ({' OR '.join(mysql_conditions)})
            LIMIT 1
            """
        elif self.dialect_name == "sqlite":
            # SQLite version using json_each() function
            # Build match conditions for each attribute
            match_conditions = []

            for i, and_group in enumerate(rule.matchers):
                and_conditions = []

                for j, attr in enumerate(and_group):
                    attr_value = alert_values.get(attr)
                    if attr_value is not None:
                        param_name = f"val_{i}_{j}"

                        # Convert value to string for comparison
                        if isinstance(attr_value, (int, float, bool)):
                            attr_value = str(attr_value)
                        elif not isinstance(attr_value, str):
                            attr_value = json.dumps(attr_value)

                        params[param_name] = attr_value

                        # Escape quotes and handle @@ for SQLite
                        attr_for_json = attr
                        if "@@" in attr_for_json:
                            attr_for_json = attr_for_json.replace("@@", ".")
                        # Escape quotes for SQLite JSON path
                        attr_for_json = attr_for_json.replace('"', '""')

                        # Build condition to check if the attribute matches or if there's a wildcard
                        and_conditions.append(
                            f"""
                            json_extract(row_data, '$."{attr_for_json}"') = :{param_name}
                            OR json_extract(row_data, '$."{attr_for_json}"') = '*'
                        """
                        )

                if and_conditions:
                    match_conditions.append(f"({' AND '.join(and_conditions)})")

            if not match_conditions:
                return None

            query = f"""
            WITH flattened AS (
                SELECT
                    value AS row_data
                FROM mappingrule, json_each(mappingrule.rows)
                WHERE mappingrule.id = :rule_id
            )
            SELECT row_data FROM flattened
            WHERE {' OR '.join(match_conditions)}
            LIMIT 1
            """
        else:
            # Default implementation (fallback to Python)
            return self._fallback_get_matching_row(rule, alert_values)

        try:
            if not self.session:
                return self._fallback_get_matching_row(rule, alert_values)

            result = self.session.execute(text(query), params).first()

            if result:
                result_dict = result[0]
                if isinstance(result_dict, str):
                    result_dict = json.loads(result_dict)
                return result_dict
            return None
        except Exception as e:
            self.logger.exception(
                f"Failed to query {self.dialect_name} for mapping rule {rule.id} due to {e}, falling back.",
                extra={
                    "tenant_id": rule.tenant_id,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                },
            )
            # Fallback to in-memory implementation
            return self._fallback_get_matching_row(rule, alert_values)

    def get_matching_rows_multi_level(
        self, rule: MappingRule, key: str, values: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get matching rows for multi-level mapping rules using SQL.

        Args:
            rule: MappingRule to check
            key: The key to match on
            values: List of values to match

        Returns:
            Dict of matched values and their corresponding enrichments
        """
        if not rule.rows or not values:
            return {}

        result = {}

        # Process matcher values and build IN condition
        clean_values = []
        value_mapping = {}

        for v in values:
            clean_v = v
            if rule.prefix_to_remove:
                clean_v = v.replace(rule.prefix_to_remove, "")
            clean_values.append(clean_v)
            value_mapping[clean_v] = v

        if not clean_values:
            return {}

        params = {"rule_id": rule.id}
        placeholder_list = []

        for i, val in enumerate(clean_values):
            param_name = f"val_{i}"
            params[param_name] = val
            placeholder_list.append(f":{param_name}")

        # Build the query based on the dialect
        if self.dialect_name == "postgresql":
            # PostgreSQL version
            in_clause = ", ".join(placeholder_list)
            query = f"""
            SELECT rows::jsonb
            FROM (
                SELECT jsonb_array_elements(rows::jsonb) AS rows
                FROM mappingrule
                WHERE id = :rule_id
            ) AS expanded_rows
            WHERE rows->>'{key}' IN ({in_clause})
            """
        elif self.dialect_name == "mysql":
            # MySQL version with proper JSON_TABLE syntax for multi-level matching
            in_clause = ", ".join(placeholder_list)

            # Handle the @@ syntax by replacing with . and wrapping in quotes
            json_key = key
            if "@@" in json_key:
                json_key = json_key.replace("@@", ".")
                json_key = f'"{json_key}"'

            query = f"""
            SELECT jt.json_object
            FROM mappingrule,
            JSON_TABLE(
                mappingrule.rows,
                '$[*]' COLUMNS (
                    sequence_number FOR ORDINALITY,
                    json_object JSON PATH '$'
                )
            ) AS jt
            WHERE mappingrule.id = :rule_id
            AND JSON_UNQUOTE(JSON_EXTRACT(jt.json_object, '$.{json_key}')) IN ({in_clause})
            """
        elif self.dialect_name == "sqlite":
            # SQLite version using json_each
            in_clause = ", ".join(placeholder_list)

            # Handle @@ and escaping in key for json_extract
            json_key = key
            if "@@" in json_key:
                json_key = json_key.replace("@@", ".")
            json_key = json_key.replace('"', '""')  # Escape quotes for SQLite JSON path

            query = f"""
            WITH flattened AS (
                SELECT
                    value AS row_data
                FROM mappingrule, json_each(mappingrule.rows)
                WHERE mappingrule.id = :rule_id
            )
            SELECT row_data FROM flattened
            WHERE json_extract(row_data, '$."{json_key}"') IN ({in_clause})
            """
        else:
            # Fallback to Python implementation for other dialects
            return self._fallback_get_matching_rows_multi_level(rule, key, values)

        try:
            if not self.session:
                return self._fallback_get_matching_rows_multi_level(rule, key, values)

            rows = self.session.execute(text(query), params).all()

            for row in rows:
                row_dict = row[0]
                if isinstance(row_dict, str):
                    row_dict = json.loads(row_dict)
                match_key = row_dict.get(key)

                if match_key in clean_values:
                    match_data = {}

                    for enrichment_key, enrichment_value in row_dict.items():
                        if enrichment_value is not None and enrichment_key != key:
                            match_data[enrichment_key.strip()] = (
                                enrichment_value.strip()
                                if isinstance(enrichment_value, str)
                                else enrichment_value
                            )

                    result[match_key] = match_data

            return result
        except Exception as e:
            self.logger.exception(
                f"Failed to query multi-level {self.dialect_name} for mapping rule {rule.id} due to {e}, falling back.",
                extra={
                    "tenant_id": rule.tenant_id,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                },
            )
            # Fallback to Python implementation
            return self._fallback_get_matching_rows_multi_level(rule, key, values)

    def _fallback_get_matching_row(
        self, rule: MappingRule, alert_values: Dict
    ) -> Optional[Dict]:
        """
        Fallback method to get matching row using in-memory iteration.

        Args:
            rule: MappingRule to check
            alert_values: Dict of alert attribute values

        Returns:
            First matching row if found, None otherwise
        """
        if not rule.rows:
            return None

        for row in rule.rows or []:
            if any(
                self._check_matcher(alert_values, row, matcher)
                for matcher in rule.matchers
            ):
                return row
        return None

    def _fallback_get_matching_rows_multi_level(
        self, rule: MappingRule, key: str, values: List[str]
    ) -> Dict[str, Dict]:
        """
        Fallback method to get matching rows for multi-level mapping using in-memory iteration.

        Args:
            rule: MappingRule to check
            key: The key to match on
            values: List of values to match

        Returns:
            Dict mapping matched values to their enrichments
        """
        result = {}

        if not rule.rows:
            return result

        for matcher_value in values:
            clean_value = matcher_value
            if rule.prefix_to_remove:
                clean_value = matcher_value.replace(rule.prefix_to_remove, "")

            for row in rule.rows:
                if row.get(key) == clean_value:
                    match_data = {}
                    for enrichment_key, enrichment_value in row.items():
                        if enrichment_value is not None and enrichment_key != key:
                            match_data[enrichment_key.strip()] = (
                                enrichment_value.strip()
                                if isinstance(enrichment_value, str)
                                else enrichment_value
                            )
                    result[clean_value] = match_data
                    break

        return result

    def _check_matcher(self, alert_values: Dict, row: Dict, matcher: List[str]) -> bool:
        """
        Check if an alert matches the conditions in a matcher.

        Args:
            alert_values: Alert values dict
            row: Row from the mapping rule
            matcher: List of attributes to match (AND condition)

        Returns:
            True if matched, False otherwise
        """
        try:
            return all(
                self._is_match(
                    alert_values.get(attribute.strip()),
                    row.get(attribute.strip()),
                )
                or alert_values.get(attribute.strip()) == row.get(attribute.strip())
                or row.get(attribute.strip()) == "*"  # Wildcard match
                for attribute in matcher
            )
        except TypeError:
            return False

    @staticmethod
    def _is_match(value, pattern):
        """
        Check if a value matches a pattern.

        Args:
            value: Value to check
            pattern: Pattern to match against

        Returns:
            True if matched, False otherwise
        """
        import re

        if value is None or pattern is None:
            return False

        # Add start and end anchors to pattern to ensure exact match
        if isinstance(pattern, str) and isinstance(value, str):
            # Only add anchors if they're not already there
            if not pattern.startswith("^"):
                pattern = f"^{pattern}"
            if not pattern.endswith("$"):
                pattern = f"{pattern}$"

        return re.search(pattern, value) is not None
