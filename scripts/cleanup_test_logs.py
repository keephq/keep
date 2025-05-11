#!/usr/bin/env python3
import os
import glob
from pathlib import Path


def cleanup_test_logs(directory: str = ".") -> tuple[int, list[str]]:
    """
    Clean up Playwright test log files and other test artifacts.
    
    Args:
        directory: The root directory to start searching from
        
    Returns:
        tuple: (number of files deleted, list of deleted files)
    """
    # Patterns to match test artifacts
    patterns = [
        "requests_playwright_dump_utils_*.log",  # Playwright request utility logs
        "requests_playwright_dump_*.log",        # Playwright request logs
        "playwright_dump_*.html",                # HTML dumps
        "playwright_dump_*.png",                 # Screenshots
        "playwright_dump_*.txt",                 # Text dumps
        "playwright_dump_*.json",                # JSON dumps
    ]
    
    deleted_files = []
    
    # Convert directory to absolute path
    abs_directory = os.path.abspath(directory)
    
    # Find and delete files matching patterns
    for pattern in patterns:
        # Use recursive glob to find files in all subdirectories
        for file_path in glob.glob(os.path.join(abs_directory, "**", pattern), recursive=True):
            try:
                os.remove(file_path)
                deleted_files.append(file_path)
            except (OSError, PermissionError) as e:
                print(f"Error deleting {file_path}: {e}")
    
    return len(deleted_files), deleted_files


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up Playwright test log files and artifacts")
    parser.add_argument("--directory", "-d", default=".",
                       help="Root directory to start searching from (default: current directory)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Print detailed information about deleted files")
    
    args = parser.parse_args()
    
    count, files = cleanup_test_logs(args.directory)
    
    print(f"Cleaned up {count} test artifact files")
    if args.verbose:
        print("\nDeleted files:")
        for file in files:
            print(f"  - {file}") 