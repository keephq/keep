"""
Keep — Alert ingestion, processing, and decision-support platform.

This package provides the core runtime for Keep, including:
- alert ingestion and normalization
- deduplication and correlation logic
- provider integrations
- action execution and orchestration
- API and service-layer primitives

IMPORTANT DESIGN NOTES
----------------------
- Importing this package MUST NOT have side effects.
- No database connections, background tasks, or network calls
  should be triggered at import time.
- Runtime initialization is handled explicitly by the application
  entrypoints (API, workers, CLI, etc.).

This file exists to:
- define the public package boundary
- document intent
- make imports predictable for contributors and tooling
"""

from __future__ import annotations

__all__ = [
    "__version__",
]

# Package version
# NOTE: Keep this in sync with pyproject.toml / setup metadata if present.
__version__ = "0.0.0"