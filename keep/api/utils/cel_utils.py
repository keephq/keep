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

    known_severities = {severity.value.lower(): severity.order for severity in AlertSeverity}
    remaining_pattern = (
        r'(\bseverity\b)\s*([=><!]=?)\s*(?:"([^"]*)"|\'([^\']*)\'|(\w+))'
    )

    def replace_remaining(match):
        value = (match.group(3) or match.group(4) or match.group(5) or "").lower()
        order = known_severities.get(value)
        if order is not None:
            return f"{match.group(1)} {match.group(2)} {order}"
        if value.isdigit():
            return match.group(0)
        return "false"

    return re.sub(
        remaining_pattern, replace_remaining, modified_expression, flags=re.IGNORECASE
    )
