#!/usr/bin/env python3

import sys
sys.path.append('/workspace')

from keep.api.utils.cel_utils import preprocess_cel_expression
from keep.api.models.alert import AlertSeverity

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
    severities = [AlertSeverity.LOW, AlertSeverity.INFO, AlertSeverity.WARNING, AlertSeverity.HIGH, AlertSeverity.CRITICAL]
    
    print("Severity ordering:")
    for severity in severities:
        print(f"  {severity.value}: {severity.order}")
    
    # Test comparisons
    comparisons = [
        (AlertSeverity.HIGH.order > AlertSeverity.INFO.order, "HIGH > INFO"),
        (AlertSeverity.CRITICAL.order > AlertSeverity.INFO.order, "CRITICAL > INFO"),
        (AlertSeverity.WARNING.order > AlertSeverity.INFO.order, "WARNING > INFO"),
        (AlertSeverity.INFO.order > AlertSeverity.LOW.order, "INFO > LOW"),
        (AlertSeverity.LOW.order < AlertSeverity.INFO.order, "LOW < INFO"),
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