import hashlib
import logging
from typing import Optional
from uuid import uuid4

from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError as SqlalchemyIntegrityError
from google.api_core.exceptions import InvalidArgument as GoogleAPIInvalidArgument

from keep.api.core.config import config
from keep.api.models.db.tenant import TenantApiKey
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.rbac import Admin as AdminRole
from keep.identitymanager.rbac import Role
from keep.identitymanager.rbac import Webhook as WebhookRole
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

logger = logging.getLogger(__name__)


class APIKeyException(Exception):
    pass


def get_api_key(
    session: Session, unique_api_key_id: str, tenant_id: str
) -> TenantApiKey:
    """
    Retrieves API key.

    Args:
        session (Session): _description_
        tenant_id (str): _description_
        unique_api_key_id (str): _description_

    Returns:
        str: _description_
    """
    # Find API key
    statement = (
        select(TenantApiKey)
        .where(TenantApiKey.reference_id == unique_api_key_id)
        .where(TenantApiKey.tenant_id == tenant_id)
    )

    api_key = session.exec(statement).first()
    return api_key


def update_api_key_internal(
    session: Session,
    tenant_id: str,
    unique_api_key_id: str,
) -> str:
    """
    Updates API key secret for the given tenant.

    Args:
        session (Session): _description_
        tenant_id (str): _description_
        unique_api_key_id (str): _description_

    Returns:
        str: _description_
    """

    # Get API Key from database
    statement = (
        select(TenantApiKey)
        .where(TenantApiKey.reference_id == unique_api_key_id)
        .where(TenantApiKey.tenant_id == tenant_id)
    )

    tenant_api_key_entry = session.exec(statement).first()

    # If no APIkey is found return
    if not tenant_api_key_entry:
        return False
    else:
        # Find current API key in secret_manager
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        # Update API key in secret_manager
        api_key = str(uuid4())

        secret_manager.write_secret(
            secret_name=f"{tenant_id}-{unique_api_key_id}",
            secret_value=api_key,
        )

        # Update API key hash in DB
        tenant_api_key_entry.key_hash = hashlib.sha256(
            api_key.encode("utf-8")
        ).hexdigest()
        session.commit()

        return api_key


def create_api_key(
    session: Session,
    tenant_id: str,
    unique_api_key_id: str,
    is_system: bool,
    created_by: str,
    role: str,
    commit: bool = True,
    system_description: Optional[str] = None,
) -> str:
    """
    Creates an API key for the given tenant.

    Args:
        session (Session): _description_
        tenant_id (str): _description_
        unique_api_key_id (str): _description_
        is_system (bool): _description_
        commit (bool, optional): _description_. Defaults to True.
        system_description (Optional[str], optional): _description_. Defaults to None.

    Returns:
        str: _description_
    """
    logger.info(
        "Creating API key",
        extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
    )
    api_key = str(uuid4())
    hashed_api_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    # Save the api key in the secret manager
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    try:
        secret_manager.write_secret(
            secret_name=f"{tenant_id}-{unique_api_key_id}",
            secret_value=api_key,
        )
        # Save the api key in the database
        new_installation_api_key = TenantApiKey(
            tenant_id=tenant_id,
            reference_id=unique_api_key_id,
            key_hash=hashed_api_key,
            is_system=is_system,
            system_description=system_description,
            created_by=created_by,
            role=role,
        )
        session.add(new_installation_api_key)

        if commit:
            session.commit()

        logger.info(
            "Created API key",
            extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
        )

        return api_key
    except SqlalchemyIntegrityError:
        raise APIKeyException("API key already exists.")
    except GoogleAPIInvalidArgument as e:
        if "does not match the expected format" in str(e):
            raise APIKeyException(str(e))
    except Exception as e:
        logger.error(
            "Error creating API key: " + str(e),
            extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
        )
        raise APIKeyException("Error creating API key.")


def get_api_keys(
    session: Session, tenant_id: str, role: Role, email: str
) -> [TenantApiKey]:
    """
    Gets all active API keys for the given tenant.

    Args:
        session (Session): _description_
        tenant_id (str): _description_

    Returns:
        str: _description_
    """

    statement = None

    if role != AdminRole:
        statement = (
            select(TenantApiKey)
            .where(TenantApiKey.tenant_id == tenant_id)
            .where(TenantApiKey.created_by == email)
            .where(TenantApiKey.is_system == False)
            .where(TenantApiKey.is_deleted != True)
        )

    else:
        statement = (
            select(TenantApiKey)
            .where(TenantApiKey.tenant_id == tenant_id)
            .where(TenantApiKey.is_system == False)
            .where(TenantApiKey.is_deleted != True)
        )

    api_keys = session.exec(statement).all()

    return api_keys


def get_api_keys_secret(
    tenant_id,
    api_keys,
):
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    api_keys_with_secret = []
    for api_key in api_keys:
        if api_key.reference_id == "webhook":
            continue

        if api_key.is_deleted == True:
            api_keys_with_secret.append(
                {
                    "reference_id": api_key.reference_id,
                    "tenant": api_key.tenant,
                    "is_deleted": api_key.is_deleted,
                    "created_at": api_key.created_at,
                    "created_by": api_key.created_by,
                    "last_used": api_key.last_used,
                    "role": api_key.role,
                    "secret": "Key has been deactivated",
                }
            )
            continue

        try:
            secret = secret_manager.read_secret(
                f"{api_key.tenant_id}-{api_key.reference_id}"
            )

            read_only_bypass_key = config("KEEP_READ_ONLY_BYPASS_KEY", default="")
            if read_only_bypass_key and read_only_bypass_key == secret:
                # Do not return the bypass key if set.
                continue

            api_keys_with_secret.append(
                {
                    "reference_id": api_key.reference_id,
                    "tenant": api_key.tenant,
                    "is_deleted": api_key.is_deleted,
                    "created_at": api_key.created_at,
                    "created_by": api_key.created_by,
                    "last_used": api_key.last_used,
                    "secret": secret,
                    "role": api_key.role,
                }
            )
        except Exception as e:
            logger.error(
                "Error reading secret",
                extra={"error": str(e)},
            )
            continue

    return api_keys_with_secret


def get_or_create_api_key(
    session: Session,
    tenant_id: str,
    created_by: str,
    unique_api_key_id: str,
    system_description: Optional[str] = None,
) -> str:
    """
    Gets or creates an API key for the given tenant.

    Args:
        session (Session): _description_
        tenant_id (str): _description_
        unique_api_key_id (str): _description_
        system_description (Optional[str], optional): _description_. Defaults to None.

    Returns:
        str: _description_
    """
    logger.info(
        "Getting or creating API key",
        extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
    )
    statement = (
        select(TenantApiKey)
        .where(TenantApiKey.reference_id == unique_api_key_id)
        .where(TenantApiKey.tenant_id == tenant_id)
    )
    tenant_api_key_entry = session.exec(statement).first()
    if not tenant_api_key_entry:
        # TODO: make it more robust
        if unique_api_key_id == "webhook":
            role = WebhookRole.get_name()
        else:
            role = AdminRole.get_name()

        tenant_api_key = create_api_key(
            session,
            tenant_id,
            unique_api_key_id,
            role=role,
            created_by=created_by,
            is_system=True,
            system_description=system_description,
        )
    else:
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        tenant_api_key = secret_manager.read_secret(f"{tenant_id}-{unique_api_key_id}")
    logger.info(
        "Got API key",
        extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
    )
    return tenant_api_key
