import re

from keep.api.models.alert import AlertSeverity


def preprocess_cel_expression(cel_expression: str) -> str:
    """Preprocess CEL expressions to replace string-based comparisons with numeric values where applicable."""

    # Construct a regex pattern that matches any severity level or other comparisons
    # and accounts for both single and double quotes as well as optional spaces around the operator
    severities = "|".join(
        [f"\"{severity.value}\"|'{severity.value}'" for severity in AlertSeverity]
    )
    pattern = rf"(\w+)\s*([=><!]=?)\s*({severities})"

    def replace_matched(match):
        field_name, operator, matched_value = (
            match.group(1),
            match.group(2),
            match.group(3).strip("\"'"),
        )

        # Handle severity-specific replacement
        if field_name.lower() == "severity":
            severity_order = next(
                (
                    severity.order
                    for severity in AlertSeverity
                    if severity.value == matched_value.lower()
                ),
                None,
            )
            if severity_order is not None:
                return f"{field_name} {operator} {severity_order}"

        # Return the original match if it's not a severity comparison or if no replacement is necessary
        return match.group(0)

    modified_expression = re.sub(
        pattern, replace_matched, cel_expression, flags=re.IGNORECASE
    )

    in_pattern = r"(\bseverity\b\s+in\s*\[)([^\]]+)(\])"

    def replace_severity_in_list(match):
        prefix = match.group(1)
        items_str = match.group(2)
        suffix = match.group(3)

        def replace_item(item_match):
            val = item_match.group(1).lower()
            severity_order = next(
                (s.order for s in AlertSeverity if s.value == val),
                None,
            )
            if severity_order is not None:
                return str(severity_order)
            return item_match.group(0)

        new_items = re.sub(r"[\"']([a-zA-Z]+)[\"']", replace_item, items_str)
        return f"{prefix}{new_items}{suffix}"

    return re.sub(
        in_pattern, replace_severity_in_list, modified_expression, flags=re.IGNORECASE
    )
