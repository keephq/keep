"""
DB model registry for SQLModel / Alembic.

Goal:
- Import all model modules once so SQLModel.metadata is populated
- Avoid `from module import *` everywhere
- Provide a stable place to manage model registration
"""

from __future__ import annotations

from importlib import import_module
from typing import Iterable

# List modules that declare SQLModel tables.
# Add/remove model modules here only.
_MODEL_MODULES: Iterable[str] = (
    "keep.api.models.db.action",
    "keep.api.models.db.ai_suggestion",
    "keep.api.models.db.alert",
    "keep.api.models.db.dashboard",
    "keep.api.models.db.extraction",
    "keep.api.models.db.facet",
    "keep.api.models.db.maintenance_window",
    "keep.api.models.db.mapping",
    "keep.api.models.db.preset",
    "keep.api.models.db.provider",
    "keep.api.models.db.rule",
    "keep.api.models.db.secret",
    "keep.api.models.db.statistics",
    "keep.api.models.db.tenant",
    "keep.api.models.db.topology",
    "keep.api.models.db.user",
    "keep.api.models.db.workflow",
)

_loaded = False


def load_models() -> None:
    """
    Import all model modules exactly once.
    Safe to call multiple times.
    """
    global _loaded
    if _loaded:
        return

    for mod in _MODEL_MODULES:
        import_module(mod)

    _loaded = True


__all__ = ["load_models"]