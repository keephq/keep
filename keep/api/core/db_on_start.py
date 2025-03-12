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
from alembic.runtime.migration import MigrationContext
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from keep.api.core.config import config
from keep.api.core.db_utils import create_db_engine
from keep.api.models.db.alert import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.dashboard import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.extraction import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.mapping import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.preset import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.provider import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.rule import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.statistics import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.tenant import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.workflow import *  # pylint: disable=unused-wildcard-import

# This import is required to create the tables
from keep.identitymanager.rbac import Admin as AdminRole

logger = logging.getLogger(__name__)

engine = create_db_engine()

KEEP_FORCE_RESET_DEFAULT_PASSWORD = config(
    "KEEP_FORCE_RESET_DEFAULT_PASSWORD", default="false", cast=bool
)
DEFAULT_USERNAME = config("KEEP_DEFAULT_USERNAME", default="keep")
DEFAULT_PASSWORD = config("KEEP_DEFAULT_PASSWORD", default="keep")


def try_create_single_tenant(tenant_id: str, create_default_user=True) -> None:
    """
    Creates the single tenant and the default user if they don't exist.
    """
    # if Keep is not multitenant, let's import the User table too:
    from keep.api.models.db.user import User  # pylint: disable=import-outside-toplevel

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
            user: User | None = session.exec(select(User)).first()
            # if no users exist, let's create the default user
            if not user and create_default_user:
                logger.info("Creating default user")

                default_password = hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()
                default_user = User(
                    username=DEFAULT_USERNAME,
                    password_hash=default_password,
                    role=AdminRole.get_name(),
                )
                session.add(default_user)
                logger.info("Default user created")
            # else, if the user want to force the refresh of the default user password
            elif KEEP_FORCE_RESET_DEFAULT_PASSWORD and user:
                # update the password of the default user
                logger.info("Forcing reset of default user password")
                default_password = hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()
                user.password_hash = default_password
                if user.username != DEFAULT_USERNAME:
                    logger.info(
                        "Default user username updated",
                        extra={
                            "username": user.username,
                            "new_username": DEFAULT_USERNAME,
                        },
                    )
                    user.username = DEFAULT_USERNAME
                logger.info("Default user password updated")
            # provision default api keys
            if os.environ.get("KEEP_DEFAULT_API_KEYS", ""):
                logger.info("Provisioning default api keys")
                from keep.contextmanager.contextmanager import ContextManager
                from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

                default_api_keys = os.environ.get("KEEP_DEFAULT_API_KEYS").split(",")
                for default_api_key in default_api_keys:
                    try:
                        api_key_name, api_key_role, api_key_secret = (
                            default_api_key.strip().split(":")
                        )
                    except ValueError:
                        logger.error(
                            "Invalid format for default api key. Expected format: name:role:secret"
                        )
                    # Create the default api key for the default user
                    api_key = session.exec(
                        select(TenantApiKey).where(
                            TenantApiKey.reference_id == api_key_name
                        )
                    ).first()
                    if api_key:
                        logger.info(f"Api key {api_key_name} already exists")
                        continue
                    logger.info(f"Provisioning api key {api_key_name}")
                    hashed_api_key = hashlib.sha256(
                        api_key_secret.encode("utf-8")
                    ).hexdigest()
                    new_installation_api_key = TenantApiKey(
                        tenant_id=tenant_id,
                        reference_id=api_key_name,
                        key_hash=hashed_api_key,
                        is_system=True,
                        created_by="system",
                        role=api_key_role,
                    )
                    session.add(new_installation_api_key)
                    # write to the secret manager
                    context_manager = ContextManager(tenant_id=tenant_id)
                    secret_manager = SecretManagerFactory.get_secret_manager(
                        context_manager
                    )
                    try:
                        secret_manager.write_secret(
                            secret_name=f"{tenant_id}-{api_key_name}",
                            secret_value=api_key_secret,
                        )
                    # probably 409 if the secret already exists, but we don't want to fail on that
                    except Exception:
                        logger.exception(
                            f"Failed to write secret for api key {api_key_name}"
                        )
                        pass
                    logger.info(f"Api key {api_key_name} provisioned")
                logger.info("Api keys provisioned")

            # commit the changes
            session.commit()
            logger.info("Single tenant created")
        except IntegrityError:
            # Tenant already exists
            logger.exception("Failed to provision single tenant")
            raise
        except Exception:
            logger.exception("Failed to create single tenant")
            pass


def migrate_db():
    """
    Run migrations to make sure the DB is up-to-date.
    """
    if os.environ.get("SKIP_DB_CREATION", "false") == "true":
        logger.info("Skipping running migrations...")
        return None

    logger.info("Running migrations...")
    config_path = os.path.dirname(os.path.abspath(__file__)) + "/../../" + "alembic.ini"
    config = alembic.config.Config(file_=config_path)
    # Re-defined because alembic.ini uses relative paths which doesn't work
    # when running the app as a pyhton pakage (could happen form any path)
    config.set_main_option(
        "script_location",
        os.path.dirname(os.path.abspath(__file__)) + "/../models/db/migrations",
    )

    try:
        alembic.command.upgrade(config, "head")
    except Exception:
        logger.exception("Failed to run migrations")

        # Log all migration file names for debugging
        script_directory = alembic.script.ScriptDirectory.from_config(config)

        # Get current revision
        try:
            with engine.begin() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                logger.error(f"Current revision: {current_rev}")
        except Exception:
            logger.exception("Failed to get current revision")
            current_rev = None

        # List all available migrations
        logger.error("Available migrations:")
        try:
            for script in script_directory.walk_revisions():
                status = (
                    "PENDING"
                    if current_rev and script.revision > current_rev
                    else "APPLIED"
                )
                logger.error(f"  - {script.revision}: {script.doc} ({status})")
        except Exception:
            logger.exception("Failed to list migrations")

        raise

    logger.info("Finished migrations")
