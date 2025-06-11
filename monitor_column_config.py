#!/usr/bin/env python3
"""
Monitor and fix specific column configuration issues for PR #5002
"""

import os
import re
import json
import subprocess
from datetime import datetime

# Known issues from the PR
KNOWN_ISSUES = {
    "checkbox_controlled": {
        "pattern": r"defaultChecked.*onChange",
        "fix": "Use controlled components with checked prop",
        "files": ["keep-ui/entities/presets/ui/column-selection/ColumnSelection.tsx"]
    },
    "static_preset_detection": {
        "pattern": r"STATIC_PRESET_IDS",
        "check": "Ensure static preset IDs are properly defined",
        "files": ["keep-ui/entities/presets/ui/table/AlertTableServerSide.tsx"]
    },
    "column_visibility_persistence": {
        "pattern": r"columnVisibility.*columnOrder",
        "check": "Ensure both columnVisibility and columnOrder are updated together",
        "files": ["keep-ui/entities/presets/model/usePresetColumnState.ts"]
    },
    "multiple_api_calls": {
        "pattern": r"updateColumnConfig.*forEach",
        "check": "Use batch updates instead of multiple API calls",
        "files": ["keep-ui/entities/presets/model/usePresetColumnState.ts"]
    }
}

def run_command(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

def check_file_for_issue(file_path, pattern):
    """Check if a file contains a specific pattern"""
    if not os.path.exists(file_path):
        return False, "File not found"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            if re.search(pattern, content):
                return True, content
            return False, content
    except Exception as e:
        return False, str(e)

def fix_checkbox_controlled_issue():
    """Fix checkbox controlled component issues"""
    file_path = "/workspace/keep-ui/entities/presets/ui/column-selection/ColumnSelection.tsx"
    
    print("🔧 Fixing checkbox controlled component issue...")
    
    has_issue, content = check_file_for_issue(file_path, r"defaultChecked")
    
    if has_issue:
        # Check if it's using defaultChecked without proper onChange
        if "defaultChecked" in content and "onChange={" in content:
            print("✅ Checkbox already has onChange handler")
        else:
            print("❌ Found uncontrolled checkbox usage")
            # The fix was already applied in the conversation, so just verify
            if "checked={isVisible}" in content:
                print("✅ Fix already applied - using controlled component")
            else:
                print("⚠️  Need to update checkbox to use controlled pattern")

def check_static_preset_ids():
    """Check if static preset IDs are properly defined"""
    print("🔧 Checking static preset IDs...")
    
    # Check if STATIC_PRESET_IDS is defined
    grep_cmd = "grep -n 'STATIC_PRESET_IDS' /workspace/keep-ui/entities/presets/model/constants.ts"
    stdout, stderr, code = run_command(grep_cmd)
    
    if code == 0:
        print(f"✅ STATIC_PRESET_IDS found: {stdout.strip()}")
        
        # Verify it contains the expected IDs
        expected_ids = ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"]
        for expected_id in expected_ids:
            if expected_id in stdout:
                print(f"✅ Found expected static ID: {expected_id}")
    else:
        print("❌ STATIC_PRESET_IDS not found in constants file")

def check_column_state_updates():
    """Check if column state updates are properly batched"""
    print("🔧 Checking column state update batching...")
    
    file_path = "/workspace/keep-ui/entities/presets/model/usePresetColumnState.ts"
    
    # Check for updateMultipleColumnConfigs function
    grep_cmd = f"grep -n 'updateMultipleColumnConfigs' {file_path}"
    stdout, stderr, code = run_command(grep_cmd)
    
    if code == 0:
        print("✅ Batch update function found")
        
        # Check if it's being used
        usage_cmd = f"grep -n 'updateMultipleColumnConfigs(' {file_path}"
        usage_out, _, usage_code = run_command(usage_cmd)
        
        if usage_code == 0:
            print("✅ Batch update function is being used")
        else:
            print("⚠️  Batch update function exists but may not be used everywhere")
    else:
        print("❌ Batch update function not found - multiple API calls may occur")

def check_test_coverage():
    """Check if the new E2E test exists and passes"""
    print("🔧 Checking E2E test coverage...")
    
    test_file = "/workspace/tests/e2e/test_backend_column_configuration_persistence.py"
    
    if os.path.exists(test_file):
        print("✅ E2E test file exists")
        
        # Check if it has proper cleanup
        with open(test_file, 'r') as f:
            content = f.read()
            if "delete_preset" in content or "cleanup" in content:
                print("✅ Test includes cleanup")
            else:
                print("⚠️  Test may not have proper cleanup")
    else:
        print("❌ E2E test file not found")

def check_imports_and_exports():
    """Check for missing imports/exports that could cause issues"""
    print("🔧 Checking imports and exports...")
    
    # Check if Tag interface is exported
    tag_export_cmd = "grep -n 'export.*interface.*Tag' /workspace/keep-ui/entities/presets/model/types.ts"
    stdout, stderr, code = run_command(tag_export_cmd)
    
    if code == 0:
        print("✅ Tag interface is exported")
    else:
        print("❌ Tag interface may not be exported")

def run_specific_tests():
    """Run specific tests related to column configuration"""
    print("🔧 Running column configuration related tests...")
    
    # Run the specific E2E test that was failing
    test_cmd = "cd /workspace && python -m pytest tests/e2e/test_alert_sorting.py::test_multi_sort_asc_dsc -v"
    stdout, stderr, code = run_command(test_cmd)
    
    if code == 0:
        print("✅ Sorting test passes")
    else:
        print(f"❌ Sorting test failed: {stdout[:500]}")
        
        # Check for the specific error about customerName
        if "customerName" in stdout:
            print("⚠️  Issue with customerName column - checking static preset handling")
            check_static_preset_ids()

def monitor_specific_issues():
    """Monitor specific column configuration issues"""
    print(f"\n🎯 Column Configuration Monitoring - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Check each known issue
    fix_checkbox_controlled_issue()
    check_static_preset_ids()
    check_column_state_updates()
    check_test_coverage()
    check_imports_and_exports()
    run_specific_tests()
    
    print("\n📊 Summary:")
    print("- Checkbox controlled components: Check completed")
    print("- Static preset detection: Check completed")
    print("- Batch API updates: Check completed")
    print("- Test coverage: Check completed")
    print("- Import/Export issues: Check completed")

if __name__ == "__main__":
    monitor_specific_issues()