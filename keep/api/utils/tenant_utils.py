import hashlib
import logging
from typing import Optional
from uuid import uuid4

from sqlmodel import Session, select

from keep.api.models.db.tenant import TenantApiKey
from keep.contextmanager.contextmanager import ContextManager
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

logger = logging.getLogger(__name__)


def create_api_key(
    session: Session,
    tenant_id: str,
    unique_api_key_id: str,
    is_system: bool,
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
    )
    session.add(new_installation_api_key)
    if commit:
        session.commit()
    logger.info(
        "Created API key",
        extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
    )
    return api_key


def get_or_create_api_key(
    session: Session,
    tenant_id: str,
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
        tenant_api_key = create_api_key(
            session,
            tenant_id,
            unique_api_key_id,
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
