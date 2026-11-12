#!/usr/bin/env python3
"""Source-checkout entry point for PostgreSQL workflow-history maintenance."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keep.cli.workflow_retention import main

if __name__ == "__main__":
    sys.exit(main())
