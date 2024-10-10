import logging
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from keep.api.core.db import get_session
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory
from keep.runbooks.runbooks_service import (
    RunbookService
    )

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{provider_type}/{provider_id}/repositories")
def get_repositories(
    provider_type: str,
    provider_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting respositories", extra={"provider_type": provider_type, "provider_id": provider_id})
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Getting provider alerts",
        extra={
            "tenant_id": tenant_id,
            "provider_type": provider_type,
            "provider_id": provider_id,
        },
    )
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    provider_config = secret_manager.read_secret(
        f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        context_manager, provider_id, provider_type, provider_config
    )

    return provider.pull_repositories()


@router.get("/{provider_type}/{provider_id}")
def get_runbook(
    provider_type: str,
    provider_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
    repo: str = Query(None),
    branch: str = Query(None),
    md_path: str = Query(None),
    title: str = Query(None),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting runbook", extra={"provider_type": provider_type, "provider_id": provider_id})
    logger.info(
        "Getting provider alerts",
        extra={
            "tenant_id": tenant_id,
            "provider_type": provider_type,
            "provider_id": provider_id,
        },
    )
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    provider_config = secret_manager.read_secret(
        f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        context_manager, provider_id, provider_type, provider_config
    )

    return provider.pull_runbook(repo=repo, branch=branch, md_path=md_path, title=title)


@router.post(
    "/{provider_type}/{provider_id}",
    description="Create a new Runbook",
    # response_model=RunbookDtoOut,
)
def create_runbook(
    provider_type: str,
    provider_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:runbook"])
    ),
    session: Session = Depends(get_session),
    repo: str = Query(None),
    branch: str = Query(None),
    md_path: str = Query(None),
    title: str = Query(None),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Creating Runbook", extra={tenant_id: tenant_id})
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    provider_config = secret_manager.read_secret(
        f"{tenant_id}_{provider_type}_{provider_id}", is_json=True
    )
    provider = ProvidersFactory.get_provider(
        context_manager, provider_id, provider_type, provider_config
    )

    runbook_dto= provider.pull_runbook(repo=repo, branch=branch, md_path=md_path, title=title)
    return RunbookService.create_runbook(session, tenant_id, runbook_dto)


@router.get(
    "",
    description="All Runbooks",
)
def get_all_runbooks(
    limit: int = 25,
    offset: int = 0,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:runbook"])
    ),
    session: Session = Depends(get_session)
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("get all Runbooks", extra={tenant_id: tenant_id})
    return RunbookService.get_all_runbooks(session, tenant_id, limit, offset)    

