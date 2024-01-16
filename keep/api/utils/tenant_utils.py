import hashlib
import logging
from typing import Optional
from uuid import uuid4

from sqlmodel import Session, select

from keep.api.core.rbac import Admin as AdminRole
from keep.api.core.rbac import Role
from keep.api.core.rbac import Webhook as WebhookRole
from keep.api.models.db.tenant import TenantApiKey
from keep.contextmanager.contextmanager import ContextManager
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

logger = logging.getLogger(__name__)


def create_api_key(
    session: Session,
    tenant_id: str,
    name: str,
    details: bool,
    created_by: str,
    role: Role,
    commit: bool = True,
) -> str:
    """
    Creates an API key for the given tenant.

    Args:
        session (Session): _description_
        tenant_id (str): _description_
        name (str): _description_
        details (bool): _description_
        commit (bool, optional): _description_. Defaults to True.
        system_description (Optional[str], optional): _description_. Defaults to None.

    Returns:
        str: _description_
    """
    logger.info(
        "Creating API key",
        extra={"tenant_id": tenant_id, "name": name},
    )
    api_key = str(uuid4())
    hashed_api_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    # Save the api key in the secret manager
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    secret_manager.write_secret(
        secret_name=f"{tenant_id}-{name}",
        secret_value=api_key,
    )
    # Save the api key in the database
    new_installation_api_key = TenantApiKey(
        tenant_id=tenant_id,
        name=name,
        details=details,
        key_hash=hashed_api_key,
        created_by=created_by,
        role=role.get_name(),
    )
    session.add(new_installation_api_key)
    if commit:
        session.commit()
    logger.info(
        "Created API key",
        extra={"tenant_id": tenant_id, "name": name},
    )
    return api_key

def update_api_key(
    session: Session,
    tenant_id: str,
    api_key_id: int,
    name: Optional[str],
    details: Optional[str],
    commit: bool = True,
) -> Optional[TenantApiKey]:
    api_key = session.get(TenantApiKey, api_key_id)
    if api_key and api_key.tenant_id == tenant_id:
        if name:
            api_key.name = name
        if details:
            api_key.details = details
        if commit:
            session.commit()
        return api_key
    return None

def delete_api_key(session: Session, tenant_id: str, api_key_id: int, commit: bool = True) -> bool:
    api_key = session.get(TenantApiKey, api_key_id)
    if api_key and api_key.tenant_id == tenant_id:
        session.delete(api_key)
        if commit:
            session.commit()
        return True
    return False


def get_or_create_api_key(
    session: Session,
    tenant_id: str,
    name: str,
    details: Optional[str],
    created_by: str,
) -> str:
    """
    Gets or creates an API key for the given tenant.

    Args:
        session (Session): _description_
        tenant_id (str): _description_
        name (str): _description_
        system_description (Optional[str], optional): _description_. Defaults to None.

    Returns:
        str: _description_
    """
    logger.info(
        "Getting or creating API key",
        extra={"tenant_id": tenant_id, "name": name},
    )
    statement = (
        select(TenantApiKey)
        .where(TenantApiKey.name == name)
        .where(TenantApiKey.tenant_id == tenant_id)
    )
    tenant_api_key_entry = session.exec(statement).first()
    if not tenant_api_key_entry:
        # TODO: make it more robust
        if name == "webhook":
            role = WebhookRole
        else:
            role = AdminRole

        tenant_api_key = create_api_key(
            session,
            tenant_id,
            name,
            details=details,
            role=role,
            created_by=created_by,
            commit=True,
        )
    else:
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        tenant_api_key = secret_manager.read_secret(f"{tenant_id}-{name}")
    logger.info(
        "Got API key",
        extra={"tenant_id": tenant_id, "name": name},
    )
    return tenant_api_key
