import os
import logging
from logging.config import fileConfig
from typing import Optional

from alembic import context
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from sqlmodel import SQLModel

import keep.api.logging
from keep.api.core.db_utils import create_db_engine

# Import models so SQLModel.metadata gets populated.
# Avoid star-imports. Import the modules for side-effect registration.
from keep.api.models.db import (  # noqa: F401
    action,
    ai_suggestion,
    alert,
    dashboard,
    extraction,
    facet,
    maintenance_window,
    mapping,
    preset,
    provider,
    secret,
    rule,
    statistics,
    tenant,
    topology,
    user,
    workflow,
)

logger = logging.getLogger("alembic.env")

target_metadata = SQLModel.metadata
config = context.config


def _is_sqlite(engine) -> bool:
    try:
        return engine.dialect.name.lower() == "sqlite"
    except Exception:
        return False


def _get_db_revision(connection) -> Optional[str]:
    """
    Return the current DB revision (as stored in alembic_version), or None if not present.
    """
    try:
        mctx = MigrationContext.configure(connection)
        return mctx.get_current_revision()
    except Exception:
        logger.exception("Failed to read current DB revision.")
        return None


def list_migrations(engine) -> None:
    """
    Print useful migration debugging info:
    - DB current revision
    - Script head(s)
    - Full revision history (local scripts)
    """
    pid = os.getpid()
    script_directory = ScriptDirectory.from_config(config)

    try:
        with engine.connect() as connection:
            db_rev = _get_db_revision(connection)

        heads = script_directory.get_heads()
        logger.warning("[%s] DB revision: %s", pid, db_rev)
        logger.warning("[%s] Script heads: %s", pid, ", ".join(heads) if heads else "NONE")

        logger.warning("[%s] Available migrations (newest -> oldest):", pid)
        for rev in script_directory.walk_revisions():
            # walk_revisions yields newest->oldest by default
            doc = (rev.doc or "").strip()
            logger.warning("  - %s  %s", rev.revision, doc)

    except Exception:
        logger.exception("Failed to list migrations.")


def run_migrations_offline() -> None:
    """
    Run migrations in OFFLINE mode.
    Generates SQL without needing a live DB connection.
    """
    engine = create_db_engine()
    url = str(engine.url)

    # Configure Alembic context for offline SQL generation.
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=_is_sqlite(engine),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in ONLINE mode with a real DB connection.
    """
    engine = create_db_engine()
    batch = _is_sqlite(engine)

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
                render_as_batch=batch,
            )

            with context.begin_transaction():
                context.run_migrations()

    except Exception:
        # Dump useful info before re-raising
        try:
            list_migrations(engine)
        finally:
            raise


# Configure logging from alembic.ini (if present)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

# Reset logs back to the app defaults after Alembic is done
keep.api.logging.setup_logging()