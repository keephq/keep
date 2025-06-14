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
import shutil

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

def get_current_revision():
    """Get current app revision"""
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return context.get_current_revision()

def copy_migrations(app_migrations_path, local_migrations_path):
    """Copy migrations to a local backup folder for safe downgrade purposes."""

    source_versions_path = os.path.join(app_migrations_path, "versions")

    # Ensure destination exists
    try:
        os.makedirs(local_migrations_path, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create local migrations folder with error: {e}")


    # Clear previous versioned migrations to ensure only migrations relevant to the current version are present
    for filename in os.listdir(local_migrations_path):
        file_path = os.path.join(local_migrations_path, filename)
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.remove(file_path)

    # Alembic needs the full migration history to safely perform a downgrade to earlier versions
    # Copy new migrations
    for item in os.listdir(source_versions_path):
        src = os.path.join(source_versions_path, item)
        dst = os.path.join(local_migrations_path, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy(src, dst)

def downgrade_db(config, expected_revision, local_migrations_path, app_migrations_path):
    """
    Downgrade the DB to the previous revision, using local backup migrations temporarily.
    Restores original migrations after downgrade.
    """
    source_versions_path = os.path.join(app_migrations_path, "versions")
    source_versions_path_copy = os.path.join(app_migrations_path, "versions_copy")

    try:
        logger.info("Backing up original migrations...")
        if os.path.exists(source_versions_path_copy):
            shutil.rmtree(source_versions_path_copy)
        shutil.move(source_versions_path, source_versions_path_copy)
        logger.info("Original migrations backed up.")

        logger.info("Restoring migrations from local backup...")
        shutil.copytree(local_migrations_path, source_versions_path)
        logger.info("Migrations restored from local.")

        logger.info("Downgrading the database...")
        alembic.command.downgrade(config, expected_revision)
        logger.info("Database successfully downgraded.")

    except Exception as e:
        logger.error(f"Error occurred during downgrade process: {e}")
    finally:
        logger.info("Restoring original migrations...")
        try:
            if os.path.exists(source_versions_path):
                shutil.rmtree(source_versions_path)
            if os.path.exists(source_versions_path_copy):
                shutil.move(source_versions_path_copy, source_versions_path)
                logger.info("Original migrations restored!")
            else:
                logger.warning("Backup not found!!! Original migrations not restored!!!")
        except Exception as restore_error:
            logger.error(f"Failed to restore original migrations: {restore_error}")

def migrate_db(config_path: str = None, app_migrations_path: str = None):
    """
    Run migrations to make sure the DB is up-to-date.
    """
    if os.environ.get("SKIP_DB_CREATION", "false") == "true":
        logger.info("Skipping running migrations...")
        return None

    config_path = config_path or os.path.dirname(os.path.abspath(__file__)) + "/../../" + "alembic.ini"
    config = alembic.config.Config(file_=config_path)
    # Re-defined because alembic.ini uses relative paths which doesn't work
    # when running the app as a pyhton pakage (could happen form any path)

    # This path will be used to save migrations locally for safe downgrade purposes
    local_migrations_path = os.environ.get("MIGRATIONS_PATH", "/tmp/keep/migrations")
    app_migrations_path = app_migrations_path or os.path.dirname(os.path.abspath(__file__)) + "/../models/db/migrations"
    config.set_main_option(
        "script_location",
        app_migrations_path,
    )
    alembic_script = alembic.script.ScriptDirectory.from_config(config)

    current_revision = get_current_revision()
    expected_revision = alembic_script.get_current_head()

    # If the current revision is the same as the expected revision, we don't need to run migrations
    if current_revision and expected_revision and current_revision == expected_revision:
        logger.info("Database schema is up-to-date!")
        return None

    logger.warning(f"Database schema ({current_revision}) doesn't match application version ({expected_revision})")
    logger.info("Running migrations...")
    try:
        alembic.command.upgrade(config, "head")
    except Exception as e:
        logger.error(f"{e} it's seems like Keep was rolled back to a previous version")

        if not os.getenv("ALLOW_DB_DOWNGRADE", "false") == "true":
            logger.error(f"ALLOW_DB_DOWNGRADE is not set to true, but the database schema ({current_revision}) doesn't match application version ({expected_revision})")
            raise RuntimeError("Database downgrade is not allowed")

        logger.info("Downgrading database schema...")
        downgrade_db(config, expected_revision, local_migrations_path, app_migrations_path)

    # Copy migrations to local folder for safe downgrade purposes
    copy_migrations(app_migrations_path, local_migrations_path)
    
    logger.info("Finished migrations")
