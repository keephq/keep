from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier, get_session
from keep.api.models import BlackoutRule
from keep.api.models.db.blackout import BlackoutRuleCreate, BlackoutRuleRead

router = APIRouter()


@router.get(
    "", response_model=list[BlackoutRuleRead], description="Get all blackout rules"
)
def get_blackout_rules(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:blackout"])
    ),
    session: Session = Depends(get_session),
) -> list[BlackoutRuleRead]:
    rules = (
        session.query(BlackoutRule)
        .filter(BlackoutRule.tenant_id == authenticated_entity.tenant_id)
        .all()
    )
    return [BlackoutRuleRead(**rule.dict()) for rule in rules]


@router.post(
    "", response_model=BlackoutRuleRead, description="Create a new blackout rule"
)
def create_blackout_rule(
    rule_dto: BlackoutRuleCreate,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:blackout"])
    ),
    session: Session = Depends(get_session),
) -> BlackoutRuleRead:
    new_rule = BlackoutRule(
        **rule_dto.dict(),
        created_by=authenticated_entity.email,
        tenant_id=authenticated_entity.tenant_id
    )
    session.add(new_rule)
    session.commit()
    session.refresh(new_rule)
    return BlackoutRuleRead(**new_rule.dict())


@router.put(
    "/{rule_id}",
    response_model=BlackoutRuleRead,
    description="Update an existing blackout rule",
)
def update_blackout_rule(
    rule_id: int,
    rule_dto: BlackoutRuleCreate,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:blackout"])
    ),
    session: Session = Depends(get_session),
) -> BlackoutRuleRead:
    rule = session.query(BlackoutRule).filter(
        BlackoutRule.tenant_id == authenticated_entity.tenant_id,
        BlackoutRule.id == rule_id,
    )
    if not rule:
        raise HTTPException(
            status_code=404, detail="Blackout rule not found or access denied"
        )
    for key, value in rule_dto.dict().items():
        setattr(rule, key, value)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return BlackoutRuleRead(**rule.dict())


@router.delete("/{rule_id}", description="Delete a blackout rule")
def delete_blackout_rule(
    rule_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:blackout"])
    ),
    session: Session = Depends(get_session),
):
    rule = session.query(BlackoutRule).filter(
        BlackoutRule.tenant_id == authenticated_entity.tenant_id,
        BlackoutRule.id == rule_id,
    )
    if not rule:
        raise HTTPException(
            status_code=404, detail="Blackout rule not found or access denied"
        )
    session.delete(rule)
    session.commit()
    return {"detail": "Blackout rule deleted successfully"}
