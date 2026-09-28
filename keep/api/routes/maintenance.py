import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keep.api.core.db import get_session
from keep.api.models.db.maintenance_window import (
    MaintenanceRuleCreate,
    MaintenanceRuleRead,
    MaintenanceWindowDto,
    MaintenanceWindowRule,
)
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_maintenance_workflows(
    tenant_id: str, maintenance: MaintenanceWindowDto, action: str
) -> None:
    from keep.workflowmanager.workflowmanager import WorkflowManager

    try:
        WorkflowManager.get_instance().insert_maintenance(
            tenant_id, maintenance, action
        )
    except Exception:
        logger.exception(
            "Failed to run workflows for maintenance window",
            extra={"maintenance_id": maintenance.id, "tenant_id": tenant_id},
        )


@router.get(
    "",
    response_model=list[MaintenanceRuleRead],
    description="Get all maintenance rules",
)
def get_maintenance_rules(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:maintenance"])
    ),
    session: Session = Depends(get_session),
) -> list[MaintenanceRuleRead]:
    rules = (
        session.query(MaintenanceWindowRule)
        .filter(MaintenanceWindowRule.tenant_id == authenticated_entity.tenant_id)
        .all()
    )
    return [MaintenanceRuleRead(**rule.dict()) for rule in rules]


@router.post(
    "", response_model=MaintenanceRuleRead, description="Create a new maintenance rule"
)
def create_maintenance_rule(
    rule_dto: MaintenanceRuleCreate,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:maintenance"])
    ),
    session: Session = Depends(get_session),
) -> MaintenanceRuleRead:
    end_time = rule_dto.start_time + timedelta(seconds=rule_dto.duration_seconds)
    new_rule = MaintenanceWindowRule(
        **rule_dto.dict(),
        end_time=end_time,
        created_by=authenticated_entity.email,
        tenant_id=authenticated_entity.tenant_id,
    )
    session.add(new_rule)
    session.commit()
    session.refresh(new_rule)
    _run_maintenance_workflows(
        authenticated_entity.tenant_id,
        MaintenanceWindowDto.from_orm_rule(new_rule),
        "created",
    )
    return MaintenanceRuleRead(**new_rule.dict())


@router.put(
    "/{rule_id}",
    response_model=MaintenanceRuleRead,
    description="Update an existing maintenance rule",
)
def update_maintenance_rule(
    rule_id: int,
    rule_dto: MaintenanceRuleCreate,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:maintenance"])
    ),
    session: Session = Depends(get_session),
) -> MaintenanceRuleRead:
    rule: MaintenanceWindowRule = (
        session.query(MaintenanceWindowRule)
        .filter(
            MaintenanceWindowRule.tenant_id == authenticated_entity.tenant_id,
            MaintenanceWindowRule.id == rule_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(
            status_code=404, detail="Maintenance rule not found or access denied"
        )

    for key, value in rule_dto.dict().items():
        setattr(rule, key, value)

    end_time = rule_dto.start_time + timedelta(seconds=rule_dto.duration_seconds)
    rule.end_time = end_time

    session.commit()
    session.refresh(rule)
    _run_maintenance_workflows(
        authenticated_entity.tenant_id,
        MaintenanceWindowDto.from_orm_rule(rule),
        "updated",
    )
    return MaintenanceRuleRead(**rule.dict())


@router.delete("/{rule_id}", description="Delete a maintenance rule")
def delete_maintenance_rule(
    rule_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:maintenance"])
    ),
    session: Session = Depends(get_session),
):
    rule = (
        session.query(MaintenanceWindowRule)
        .filter(
            MaintenanceWindowRule.tenant_id == authenticated_entity.tenant_id,
            MaintenanceWindowRule.id == rule_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(
            status_code=404, detail="Maintenance rule not found or access denied"
        )
    maintenance = MaintenanceWindowDto.from_orm_rule(rule)
    session.delete(rule)
    session.commit()
    _run_maintenance_workflows(authenticated_entity.tenant_id, maintenance, "deleted")
    return {"detail": "Maintenance rule deleted successfully"}
