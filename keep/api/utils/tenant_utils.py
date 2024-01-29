import hashlib
import logging
from typing import Optional
from uuid import uuid4
from datetime import datetime

from sqlmodel import Session, select

from keep.api.core.rbac import Admin as AdminRole
from keep.api.core.rbac import Role
from keep.api.core.rbac import Webhook as WebhookRole
from keep.api.models.db.tenant import TenantApiKey
from keep.contextmanager.contextmanager import ContextManager
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

logger = logging.getLogger(__name__)


def delete_api_key_internal(
    session: Session,
    tenant_id: str,
    unique_api_key_id: str,
) -> str:
    """
    Deletes API key for the given tenant.

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

    if api_key:
        # Delete from database
        session.delete(api_key)
        session.commit()

        # Delete from secret manager
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)

        secret_manager.delete_secret(
            secret_name=f"{tenant_id}-{unique_api_key_id}",
        )

        return True
    return False


def update_key_last_used(
    session: Session,
    tenant_id: str,
    unique_api_key_id: str,
) -> str:
    """
    Updates API key last used.

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

    # Update last used
    tenant_api_key_entry.last_used = datetime.utcnow()
    session.commit()


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
        old_api_key_secret = secret_manager.read_secret(
                f"{tenant_id}-{unique_api_key_id}"
        )

        # Update API key in secret_manager
        api_key = str(uuid4())

        secret_manager.write_secret(
            secret_name=f"{tenant_id}-{unique_api_key_id}",
            secret_value=api_key,
        )

        # Update API key hash in DB
        tenant_api_key_entry.key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        session.commit()

        return api_key


def create_api_key(
    session: Session,
    tenant_id: str,
    unique_api_key_id: str,
    is_system: bool,
    created_by: str,
    role: Role,
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
        role=role.get_name(),
    )
    session.add(new_installation_api_key)

    if commit:
        session.commit()

    logger.info(
        "Created API key",
        extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
    )

    if is_system:
        return api_key

    else:
        statement = (
            select(TenantApiKey)
            .where(TenantApiKey.tenant_id == tenant_id)
            .where(TenantApiKey.reference_id == new_installation_api_key.reference_id)
        )

        new_api_key = session.exec(statement).first()
        return {**vars(new_api_key), "secret": api_key}


def get_api_keys(
    session: Session,
    tenant_id: str,
    role: str,
    email: str
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

    if role != 'admin':
        statement = (
            select(TenantApiKey)
            .where(TenantApiKey.tenant_id == tenant_id)
            .where(TenantApiKey.created_by == email)
        )

    else:
        statement = (
            select(TenantApiKey)
            .where(TenantApiKey.tenant_id == tenant_id)
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
        secret = secret_manager.read_secret(
                f"{api_key.tenant_id}-{api_key.reference_id}"
        )
        api_keys_with_secret.append({**vars(api_key), "secret": secret})

    return api_keys_with_secret


def get_or_create_api_key(
    session: Session,
    tenant_id: str,
    created_by: str,
    unique_api_key_id: str,
    system_description: Optional[str] = None,
):
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
            role = WebhookRole
        else:
            role = AdminRole

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
