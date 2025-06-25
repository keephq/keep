#!/usr/bin/env python3

import os
import sys
import re

# Add the workspace to the path
sys.path.insert(0, '/workspace')

def create_mock_alert_severity():
    """Create a mock AlertSeverity class to test the preprocessing"""
    class MockAlertSeverity:
        def __init__(self, value, order):
            self.value = value
            self.order = order
    
    # Return instances, not a class
    return [
        MockAlertSeverity("low", 1),
        MockAlertSeverity("info", 2), 
        MockAlertSeverity("warning", 3),
        MockAlertSeverity("high", 4),
        MockAlertSeverity("critical", 5)
    ]

def preprocess_cel_expression(cel_expression: str) -> str:
    """Preprocess CEL expressions to replace string-based comparisons with numeric values where applicable."""
    
    # Create mock AlertSeverity for testing
    alert_severities = create_mock_alert_severity()
    
    # Construct a regex pattern that matches any severity level or other comparisons
    # and accounts for both single and double quotes as well as optional spaces around the operator
    severities = "|".join(
        [f"\"{severity.value}\"|'{severity.value}'" for severity in alert_severities]
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
                    for severity in alert_severities
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

    return modified_expression

def test_severity_preprocessing():
    """Test that severity comparisons are preprocessed correctly"""
    
    print("Testing severity preprocessing...")
    
    # Test cases from the bug report
    test_cases = [
        # Original expression -> Expected result
        ("severity > 'info'", "severity > 2"),
        ("severity >= 'warning'", "severity >= 3"),
        ("severity < 'high'", "severity < 4"),
        ("severity <= 'critical'", "severity <= 5"),
        ("severity == 'info'", "severity == 2"),
        # Complex expressions
        ("severity > 'info' && source.contains('prometheus')", "severity > 2 && source.contains('prometheus')"),
        ("(severity >= 'warning' && source.contains('prometheus')) || (severity == 'critical' && source.contains('grafana'))", "(severity >= 3 && source.contains('prometheus')) || (severity == 5 && source.contains('grafana'))"),
        # Case insensitive
        ("severity > 'INFO'", "severity > 2"),
        ("severity >= 'Warning'", "severity >= 3"),
        # Different quote styles
        ('severity > "info"', 'severity > 2'),
        ('severity >= "warning"', 'severity >= 3'),
        # Non-severity fields should not be changed
        ("name == 'info'", "name == 'info'"),
        ("status == 'critical'", "status == 'critical'"),
    ]
    
    all_passed = True
    
    for original, expected in test_cases:
        result = preprocess_cel_expression(original)
        if result == expected:
            print(f"✓ PASS: '{original}' -> '{result}'")
        else:
            print(f"✗ FAIL: '{original}' -> '{result}' (expected: '{expected}')")
            all_passed = False
    
    return all_passed

def test_severity_ordering():
    """Test that severity ordering is correct"""
    
    print("\nTesting severity ordering...")
    
    # Test the AlertSeverity enum ordering
    alert_severities = create_mock_alert_severity()
    
    print("Severity ordering:")
    for severity in alert_severities:
        print(f"  {severity.value}: {severity.order}")
    
    # Test comparisons using the order field
    comparisons = [
        (alert_severities[3].order > alert_severities[1].order, "HIGH > INFO"),  # high > info
        (alert_severities[4].order > alert_severities[1].order, "CRITICAL > INFO"),  # critical > info
        (alert_severities[2].order > alert_severities[1].order, "WARNING > INFO"),  # warning > info
        (alert_severities[1].order > alert_severities[0].order, "INFO > LOW"),  # info > low
        (alert_severities[0].order < alert_severities[1].order, "LOW < INFO"),  # low < info
    ]
    
    all_passed = True
    
    for result, description in comparisons:
        if result:
            print(f"✓ PASS: {description}")
        else:
            print(f"✗ FAIL: {description}")
            all_passed = False
    
    return all_passed

def main():
    print("=" * 60)
    print("Testing Severity CEL Expression Preprocessing Fix")
    print("=" * 60)
    
    # Test the preprocessing function
    preprocessing_passed = test_severity_preprocessing()
    
    # Test severity ordering
    ordering_passed = test_severity_ordering()
    
    print("\n" + "=" * 60)
    if preprocessing_passed and ordering_passed:
        print("🎉 ALL TESTS PASSED! The severity comparison fix should work correctly.")
        print("\nBug Analysis:")
        print("- Before fix: 'severity > \"info\"' was compared lexicographically")
        print("  - 'high' < 'info' lexicographically (h < i)")
        print("  - 'warning' > 'info' lexicographically (w > i)")
        print("- After fix: 'severity > \"info\"' becomes 'severity > 2'")
        print("  - high (4) > info (2) ✓")
        print("  - warning (3) > info (2) ✓")
        print("  - critical (5) > info (2) ✓")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())