#!/usr/bin/env python3
"""
Main monitoring script for PR #5002
Runs every 10 seconds to check and fix issues
"""

import os
import time
import subprocess
import sys
from datetime import datetime

# Import our specific monitors
sys.path.append('/workspace')

def run_command(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

def simulate_github_actions():
    """Simulate what GitHub Actions would run"""
    print("\n🔄 Simulating GitHub Actions checks...")
    
    actions = {
        "TypeScript Lint": "cd /workspace/keep-ui && npm run lint",
        "TypeScript Build": "cd /workspace/keep-ui && npm run build",
        "UI Tests": "cd /workspace/keep-ui && npm test -- --passWithNoTests",
        "Python Lint": "cd /workspace && python -m ruff check keep/",
        "Python Tests": "cd /workspace && python -m pytest tests/test_utils.py -v",
        "E2E Test (Sorting)": "cd /workspace && python -m pytest tests/e2e/test_alert_sorting.py::test_multi_sort_asc_dsc -v --timeout=30"
    }
    
    results = {}
    
    for action_name, command in actions.items():
        print(f"\n🏃 Running: {action_name}")
        stdout, stderr, returncode = run_command(command + " 2>&1 | head -50")
        
        if returncode == 0:
            print(f"✅ {action_name}: PASSED")
            results[action_name] = "PASSED"
        else:
            print(f"❌ {action_name}: FAILED")
            print(f"   Output: {stdout[:200]}")
            results[action_name] = "FAILED"
            
            # Attempt auto-fix based on the failure
            auto_fix_issue(action_name, stdout + stderr)
    
    return results

def auto_fix_issue(action_name, output):
    """Attempt to automatically fix common issues"""
    print(f"🔧 Attempting to fix {action_name}...")
    
    if action_name == "TypeScript Lint":
        # Try auto-fix
        fix_cmd = "cd /workspace/keep-ui && npm run lint:fix"
        stdout, stderr, code = run_command(fix_cmd)
        if code == 0:
            print("✅ Lint issues auto-fixed")
            # Commit the changes
            run_command("cd /workspace && git add -A && git commit -m 'fix: auto-fix linting issues' 2>&1")
    
    elif action_name == "UI Tests" and "Cannot find module" in output:
        print("📦 Installing missing dependencies...")
        run_command("cd /workspace/keep-ui && npm install")
    
    elif action_name == "Python Lint":
        fix_cmd = "cd /workspace && python -m ruff check --fix keep/"
        stdout, stderr, code = run_command(fix_cmd)
        if "fixed" in stdout:
            print("✅ Python lint issues auto-fixed")
            run_command("cd /workspace && git add -A && git commit -m 'fix: auto-fix Python linting' 2>&1")
    
    elif action_name == "E2E Test (Sorting)" and "customerName" in output:
        print("🔍 Checking static preset handling...")
        # Run the column config monitor
        run_command("python /workspace/monitor_column_config.py")

def check_pr_specific_issues():
    """Check for PR #5002 specific issues"""
    print("\n🎯 Checking PR #5002 specific issues...")
    
    # Run the column configuration monitor
    stdout, stderr, code = run_command("python /workspace/monitor_column_config.py")
    print(stdout)

def generate_status_report(results):
    """Generate a status report"""
    print("\n" + "="*60)
    print("📊 STATUS REPORT")
    print("="*60)
    
    total = len(results)
    passed = sum(1 for status in results.values() if status == "PASSED")
    failed = total - passed
    
    print(f"Total checks: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed > 0:
        print("\n⚠️  Failed checks:")
        for check, status in results.items():
            if status == "FAILED":
                print(f"  - {check}")
    
    print("\n" + "="*60)

def main_monitoring_loop():
    """Main monitoring loop that runs every 10 seconds"""
    iteration = 0
    
    print("🚀 Starting PR #5002 monitoring system")
    print("Monitoring every 10 seconds. Press Ctrl+C to stop.\n")
    
    while True:
        try:
            iteration += 1
            print(f"\n{'='*80}")
            print(f"🔍 MONITORING ITERATION #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}")
            
            # First, ensure dependencies are installed
            print("\n📦 Checking dependencies...")
            run_command("cd /workspace/keep-ui && npm install --no-audit --no-fund 2>&1 | tail -5")
            
            # Run GitHub Actions simulation
            results = simulate_github_actions()
            
            # Check PR-specific issues
            check_pr_specific_issues()
            
            # Generate status report
            generate_status_report(results)
            
            # If all checks pass, show success
            if all(status == "PASSED" for status in results.values()):
                print("\n🎉 All checks are passing! PR #5002 is ready.")
            else:
                print("\n⚠️  Some checks are failing. Auto-fixes have been attempted.")
                print("Manual intervention may be required for remaining issues.")
            
            print(f"\n⏳ Next check in 10 seconds... (Iteration {iteration} complete)")
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped by user")
            print(f"Completed {iteration} monitoring iterations")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            print("Continuing monitoring...")
            time.sleep(10)

if __name__ == "__main__":
    # Make scripts executable
    os.chmod('/workspace/monitor_pr.py', 0o755)
    os.chmod('/workspace/monitor_column_config.py', 0o755)
    
    main_monitoring_loop()