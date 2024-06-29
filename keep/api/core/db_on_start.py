"""
This module is responsible for creating the database and tables when the application starts.

The reason to split this code from db.py is that the functions here are invoked from the master process
when the application starts, while the functions in db.py are invoked from the worker processes.

This is important because if the master process init the engine, it will be forked to the worker processes,
and the engine will be shared among all the processes, causing issues with the connections.
"""

import hashlib
import logging
import os

from sqlalchemy.exc import IntegrityError
from sqlalchemy_utils import create_database, database_exists
from sqlmodel import Session, SQLModel, select

from keep.api.core.db_utils import create_db_engine

# This import is required to create the tables
from keep.api.core.rbac import Admin as AdminRole
from keep.api.models.db.alert import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.dashboard import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.extraction import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.mapping import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.preset import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.provider import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.rule import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.tenant import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.workflow import *  # pylint: disable=unused-wildcard-import

logger = logging.getLogger(__name__)

engine = create_db_engine()


def try_create_single_tenant(tenant_id: str) -> None:
    """
    Creates the single tenant and the default user if they don't exist.
    """
    try:
        # if Keep is not multitenant, let's import the User table too:
        from keep.api.models.db.user import (  # pylint: disable=import-outside-toplevel
            User,
        )

        create_db_and_tables()
    except Exception:
        pass
    with Session(engine) as session:
        try:
            # check if the tenant exist:
            tenant = session.exec(select(Tenant).where(Tenant.id == tenant_id)).first()
            if not tenant:
                # Do everything related with single tenant creation in here
                logger.info("Creating single tenant")
                session.add(Tenant(id=tenant_id, name="Single Tenant"))
            else:
                logger.info("Single tenant already exists")

            # now let's create the default user

            # check if at least one user exists:
            user = session.exec(select(User)).first()
            # if no users exist, let's create the default user
            if not user:
                default_username = os.environ.get("KEEP_DEFAULT_USERNAME", "keep")
                default_password = hashlib.sha256(
                    os.environ.get("KEEP_DEFAULT_PASSWORD", "keep").encode()
                ).hexdigest()
                default_user = User(
                    username=default_username,
                    password_hash=default_password,
                    role=AdminRole.get_name(),
                )
                session.add(default_user)
            # else, if the user want to force the refresh of the default user password
            elif os.environ.get("KEEP_FORCE_RESET_DEFAULT_PASSWORD", "false") == "true":
                # update the password of the default user
                default_password = hashlib.sha256(
                    os.environ.get("KEEP_DEFAULT_PASSWORD", "keep").encode()
                ).hexdigest()
                user.password_hash = default_password
            # commit the changes
            session.commit()
            logger.info("Single tenant created")
        except IntegrityError:
            # Tenant already exists
            logger.info("Single tenant already exists")
            pass
        except Exception:
            logger.exception("Failed to create single tenant")
            pass


def create_db_and_tables():
    """
    Creates the database and tables.
    """
    try:
        if not database_exists(engine.url):
            logger.info("Creating the database")
            create_database(engine.url)
            logger.info("Database created")
    # On Cloud Run, it fails to check if the database exists
    except Exception:
        logger.warning("Failed to create the database or detect if it exists.")
        pass

    logger.info("Creating the tables")
    SQLModel.metadata.create_all(engine)
    logger.info("Tables created")
