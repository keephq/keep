"""
This module is responsible for creating the database and tables when the application starts.

The reason to split this code from db.py is that the functions here are invoked from the master process
when the application starts, while the functions in db.py are invoked from the worker processes.

This is important because if the master process init the engine, it will be forked to the worker processes,
and the engine will be shared among all the processes, causing issues with the connections.

** This happens because the engine is not fork-safe, and the connections are not thread-safe. **

The mitigation is to create different engines for each process, and the master process should only be responsible
for creating the database and tables, while the worker processes should only be responsible for creating the sessions.
"""

import hashlib
import logging
import os

import alembic.command
import alembic.config

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

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

        migrate_db()
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



def migrate_db():
    """
    Run migrations to make sure the DB is up-to-date.
    """
    logger.info("Running migrations...")
    config_path = os.path.dirname(os.path.abspath(__file__)) + "/../../" + "alembic.ini"
    config = alembic.config.Config(file_=config_path)
    # Re-defined because alembic.ini uses relative paths which doesn't work 
    # when running the app as a pyhton pakage (could happen form any path)
    config.set_main_option("script_location", os.path.dirname(os.path.abspath(__file__)) + "/../models/db/migrations")
    alembic.command.upgrade(config, "head")
    logger.info("Finished migrations")
