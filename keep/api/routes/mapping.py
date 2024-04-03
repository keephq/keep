import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keep.api.core.db import get_session
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.db.mapping import (
    MappingRule,
    MappingRuleDtoIn,
    MappingRuleDtoOut,
    MappingRuleDtoUpdate,
)

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("", description="Get all mapping rules")
def get_rules(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:rules"])),
    session: Session = Depends(get_session),
) -> list[MappingRuleDtoOut]:
    logger.info("Getting mapping rules")
    rules: list[MappingRule] = (
        session.query(MappingRule)
        .filter(MappingRule.tenant_id == authenticated_entity.tenant_id)
        .all()
    )
    logger.info("Got mapping rules", extra={"rules_count": len(rules) if rules else 0})

    rules_dtos = []
    if rules:
        for rule in rules:
            rule_dto = MappingRuleDtoOut(**rule.dict())
            rule_dto.attributes = [
                key for key in rule.rows[0].keys() if key not in rule.matchers
            ]
            rules_dtos.append(rule_dto)

    return rules_dtos


@router.post(
    "",
    description="Create a new mapping rule",
    response_model_exclude={"rows", "tenant_id"},
)
def create_rule(
    rule: MappingRuleDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:rules"])),
    session: Session = Depends(get_session),
) -> MappingRule:
    logger.info("Creating a new mapping rule")
    new_rule = MappingRule(
        **rule.dict(),
        tenant_id=authenticated_entity.tenant_id,
        created_by=authenticated_entity.email,
    )
    session.add(new_rule)
    session.commit()
    session.refresh(new_rule)
    logger.info("Created a new mapping rule", extra={"rule_id": new_rule.id})
    return new_rule


@router.delete("/{rule_id}", description="Delete a mapping rule")
def delete_rule(
    rule_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:rules"])),
    session: Session = Depends(get_session),
):
    logger.info("Deleting a mapping rule", extra={"rule_id": rule_id})
    rule = (
        session.query(MappingRule)
        .filter(MappingRule.id == rule_id)
        .filter(MappingRule.tenant_id == authenticated_entity.tenant_id)
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()
    logger.info("Deleted a mapping rule", extra={"rule_id": rule_id})
    return {"message": "Rule deleted successfully"}


@router.put("", description="Update an existing rule")
def update_rule(
    rule: MappingRuleDtoUpdate,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["write:rules"])),
    session: Session = Depends(get_session),
) -> MappingRuleDtoOut:
    logger.info("Updating a mapping rule")
    existing_rule: MappingRule = (
        session.query(MappingRule)
        .filter(
            MappingRule.tenant_id == authenticated_entity.tenant_id,
            MappingRule.id == rule.id,
        )
        .first()
    )
    if existing_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    existing_rule.name = rule.name
    existing_rule.description = rule.description
    existing_rule.matchers = rule.matchers
    existing_rule.file_name = rule.file_name
    existing_rule.priority = rule.priority
    if rule.rows is not None:
        existing_rule.rows = rule.rows
    session.commit()
    session.refresh(existing_rule)
    response = MappingRuleDtoOut(**existing_rule.dict())
    if rule.rows is not None:
        response.attributes = [
            key for key in existing_rule.rows[0].keys() if key not in rule.matchers
        ]
    return response
