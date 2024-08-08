import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.future import Connection
from sqlmodel import SQLModel

import keep.api.logging
from keep.api.core.db_utils import create_db_engine
from keep.api.models.db.action import *
from keep.api.models.db.alert import *
from keep.api.models.db.dashboard import *
from keep.api.models.db.extraction import *
from keep.api.models.db.mapping import *
from keep.api.models.db.preset import *
from keep.api.models.db.provider import *
from keep.api.models.db.rule import *
from keep.api.models.db.tenant import *
from keep.api.models.db.topology import *
from keep.api.models.db.user import *
from keep.api.models.db.workflow import *
from keep.api.models.db.statistics import *

target_metadata = SQLModel.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    # backup the current config
    logging_config = config.get_section("loggers")
    fileConfig(config.config_file_name)


async def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    connectable = create_db_engine()
    context.configure(
        url=str(connectable.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Run actual sync migrations.

    :param connection: connection to the database.
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = create_db_engine()
    do_run_migrations(connectable.connect())


loop = asyncio.get_event_loop()
if context.is_offline_mode():
    task = run_migrations_offline()
else:
    task = run_migrations_online()

loop.run_until_complete(task)
# SHAHAR: set back the logs to the default after alembic is done
keep.api.logging.setup_logging()
