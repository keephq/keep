import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keep.api.core.db import get_session
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.db.extraction import (
    ExtractionRule,
    ExtractionRuleDtoBase,
    ExtractionRuleDtoOut,
)

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("", description="Get all extraction rules")
def get_extraction_rules(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:extraction"])
    ),
    session: Session = Depends(get_session),
) -> list[ExtractionRuleDtoOut]:
    logger.info("Getting extraction rules")
    rules = (
        session.query(ExtractionRule)
        .filter(ExtractionRule.tenant_id == authenticated_entity.tenant_id)
        .all()
    )
    return [ExtractionRuleDtoOut(**rule.dict()) for rule in rules]


@router.post("", description="Create a new extraction rule")
def create_extraction_rule(
    rule_dto: ExtractionRuleDtoBase,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:extraction"])
    ),
    session: Session = Depends(get_session),
) -> ExtractionRuleDtoOut:
    logger.info("Creating a new extraction rule")
    new_rule = ExtractionRule(
        **rule_dto.dict(),
        created_by=authenticated_entity.email,
        tenant_id=authenticated_entity.tenant_id
    )
    session.add(new_rule)
    session.commit()
    session.refresh(new_rule)
    return ExtractionRuleDtoOut(**new_rule.dict())


@router.put("/{rule_id}", description="Update an existing extraction rule")
def update_extraction_rule(
    rule_id: int,
    rule_dto: ExtractionRuleDtoBase,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:extraction"])
    ),
    session: Session = Depends(get_session),
) -> ExtractionRuleDtoOut:
    logger.info("Updating an extraction rule")
    rule: ExtractionRule | None = (
        session.query(ExtractionRule)
        .filter(
            ExtractionRule.id == rule_id,
            ExtractionRule.tenant_id == authenticated_entity.tenant_id,
        )
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    for key, value in rule_dto.dict(exclude_unset=True).items():
        setattr(rule, key, value)
    rule.updated_by = authenticated_entity.email
    rule.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.commit()
    session.refresh(rule)
    return ExtractionRuleDtoOut(**rule.dict())


@router.delete("/{rule_id}", description="Delete an extraction rule")
def delete_extraction_rule(
    rule_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:extraction"])
    ),
    session: Session = Depends(get_session),
):
    logger.info("Deleting an extraction rule")
    rule = (
        session.query(ExtractionRule)
        .filter(
            ExtractionRule.id == rule_id,
            ExtractionRule.tenant_id == authenticated_entity.tenant_id,
        )
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Extraction rule not found")
    session.delete(rule)
    session.commit()
    return {"message": "Extraction rule deleted successfully"}
