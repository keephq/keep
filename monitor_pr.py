#!/usr/bin/env python3
"""
Monitor PR #5002 and automatically fix common issues
"""

import os
import time
import subprocess
import re
from datetime import datetime

# Common issues and their fixes
COMMON_FIXES = {
    # TypeScript/ESLint issues
    r"Missing return type on function": "Add explicit return types to functions",
    r"'(\w+)' is defined but never used": "Remove unused imports/variables",
    r"Expected '===' and instead saw '=='": "Replace == with ===",
    r"Missing semicolon": "Add missing semicolons",
    
    # Python issues
    r"E501 line too long": "Break long lines",
    r"imported but unused": "Remove unused imports",
    r"undefined name": "Import missing modules",
    
    # Test failures
    r"Cannot find module": "Check imports and module paths",
    r"Test.*failed": "Review test logic and assertions",
    
    # Build issues
    r"Module not found": "Run npm install or pip install",
    r"Command not found": "Install missing dependencies",
}

def run_command(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

def check_typescript_issues():
    """Check for TypeScript/ESLint issues in keep-ui"""
    print("Checking TypeScript/ESLint issues...")
    stdout, stderr, code = run_command("cd /workspace/keep-ui && npm run lint 2>&1")
    
    if code != 0:
        print(f"❌ Linting issues found:\n{stdout}\n{stderr}")
        
        # Try to auto-fix
        print("Attempting auto-fix...")
        fix_stdout, fix_stderr, fix_code = run_command("cd /workspace/keep-ui && npm run lint:fix 2>&1")
        
        if fix_code == 0:
            print("✅ Auto-fix successful!")
            # Commit the fixes
            run_command("cd /workspace && git add -A && git commit -m 'fix: auto-fix linting issues' 2>&1")
        else:
            print(f"⚠️  Auto-fix failed: {fix_stdout}\n{fix_stderr}")
            analyze_and_fix_specific_issues(stdout + stderr)
    else:
        print("✅ No linting issues found")

def check_python_issues():
    """Check for Python linting issues"""
    print("Checking Python issues...")
    stdout, stderr, code = run_command("cd /workspace && python -m ruff check keep/ 2>&1")
    
    if code != 0:
        print(f"❌ Python linting issues found:\n{stdout}\n{stderr}")
        
        # Try to auto-fix
        print("Attempting auto-fix...")
        fix_stdout, fix_stderr, fix_code = run_command("cd /workspace && python -m ruff check --fix keep/ 2>&1")
        
        if "fixed" in fix_stdout.lower():
            print("✅ Auto-fix successful!")
            run_command("cd /workspace && git add -A && git commit -m 'fix: auto-fix Python linting issues' 2>&1")
        else:
            print(f"⚠️  Some issues require manual fixes: {fix_stdout}")
    else:
        print("✅ No Python linting issues found")

def check_test_failures():
    """Check for test failures and common issues"""
    print("Checking for test failures...")
    
    # Check UI tests
    stdout, stderr, code = run_command("cd /workspace/keep-ui && npm test -- --passWithNoTests 2>&1 | head -100")
    if "FAIL" in stdout or code != 0:
        print(f"❌ UI test failures detected:\n{stdout[:500]}")
        analyze_test_failures(stdout)
    
    # Check Python tests
    stdout, stderr, code = run_command("cd /workspace && python -m pytest tests/ -v --tb=short 2>&1 | head -100")
    if "FAILED" in stdout or code != 0:
        print(f"❌ Python test failures detected:\n{stdout[:500]}")
        analyze_test_failures(stdout)

def analyze_and_fix_specific_issues(output):
    """Analyze specific issues and attempt targeted fixes"""
    # Check for missing imports in TypeScript
    if "Cannot find module" in output:
        match = re.search(r"Cannot find module '([^']+)'", output)
        if match:
            module = match.group(1)
            if module.startswith("@/"):
                print(f"⚠️  Missing internal module: {module}")
                # Check if the file exists
                check_module_exists(module)
    
    # Check for undefined variables
    if "is not defined" in output:
        match = re.search(r"'(\w+)' is not defined", output)
        if match:
            var_name = match.group(1)
            print(f"⚠️  Undefined variable: {var_name}")
            suggest_import_for_variable(var_name)

def check_module_exists(module_path):
    """Check if a module file exists"""
    # Convert @/ to keep-ui/
    file_path = module_path.replace("@/", "/workspace/keep-ui/")
    
    # Check with different extensions
    for ext in [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx"]:
        full_path = file_path + ext
        if os.path.exists(full_path):
            print(f"✅ Module exists at: {full_path}")
            return
    
    print(f"❌ Module not found. Expected at: {file_path}")

def suggest_import_for_variable(var_name):
    """Suggest imports for undefined variables"""
    common_imports = {
        "React": "import React from 'react';",
        "useState": "import { useState } from 'react';",
        "useEffect": "import { useEffect } from 'react';",
        "useMemo": "import { useMemo } from 'react';",
        "useCallback": "import { useCallback } from 'react';",
    }
    
    if var_name in common_imports:
        print(f"💡 Suggestion: Add this import: {common_imports[var_name]}")

def analyze_test_failures(output):
    """Analyze test failures and suggest fixes"""
    if "Cannot find module" in output:
        print("💡 Test import issues detected. Running npm install...")
        run_command("cd /workspace/keep-ui && npm install")
    
    if "Timeout" in output:
        print("💡 Test timeout detected. Consider increasing timeout or optimizing test")
    
    if "Expected" in output and "Received" in output:
        print("💡 Assertion failure. Review test expectations")

def check_dependencies():
    """Check and install missing dependencies"""
    print("Checking dependencies...")
    
    # Check npm dependencies
    stdout, stderr, code = run_command("cd /workspace/keep-ui && npm ls 2>&1 | grep 'npm ERR!' | head -10")
    if stdout:
        print("❌ Missing npm dependencies detected")
        print("Installing dependencies...")
        run_command("cd /workspace/keep-ui && npm install")
    
    # Check Python dependencies
    stdout, stderr, code = run_command("cd /workspace && pip check 2>&1")
    if code != 0:
        print("❌ Python dependency issues detected")
        print("Installing dependencies...")
        run_command("cd /workspace && pip install -e . -r requirements.txt")

def monitor_loop():
    """Main monitoring loop"""
    iteration = 0
    
    while True:
        iteration += 1
        print(f"\n{'='*60}")
        print(f"🔍 Monitoring iteration #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        try:
            # Check dependencies first
            check_dependencies()
            
            # Check for various issues
            check_typescript_issues()
            check_python_issues()
            check_test_failures()
            
            print("\n✅ Monitoring cycle complete. Waiting 10 seconds...")
            
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped by user")
            break
        except Exception as e:
            print(f"\n❌ Error during monitoring: {e}")
        
        time.sleep(10)

if __name__ == "__main__":
    print("🚀 Starting PR #5002 monitoring...")
    print("Press Ctrl+C to stop\n")
    monitor_loop()