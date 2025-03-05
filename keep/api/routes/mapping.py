import datetime
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.db import get_session
from keep.api.models.db.enrichment_event import EnrichmentEventWithLogs
from keep.api.models.db.mapping import (
    MappingRule,
    MappingRuleDtoIn,
    MappingRuleDtoOut,
    MappingRuleUpdateDtoIn,
)
from keep.api.models.db.topology import TopologyService
from keep.api.utils.pagination import EnrichmentEventPaginatedResultsDto
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("", description="Get all mapping rules")
def get_rules(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:rules"])
    ),
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

            attributes = []
            if rule_dto.type == "csv":
                attributes = [
                    key
                    for key in rule.rows[0].keys()
                    if not any(key in matcher for matcher in rule.matchers)
                ]
            elif rule_dto.type == "topology":
                attributes = [
                    field
                    for field in TopologyService.__fields__
                    if field not in rule.matchers
                    and field != "tenant_id"
                    and field != "id"
                ]

            rule_dto.attributes = attributes
            rules_dtos.append(rule_dto)

    return rules_dtos


@router.post(
    "",
    description="Create a new mapping rule",
    response_model_exclude={"rows", "tenant_id"},
)
def create_rule(
    rule: MappingRuleDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:rules"])
    ),
    session: Session = Depends(get_session),
) -> MappingRule:
    logger.info("Creating a new mapping rule")
    new_rule = MappingRule(
        **rule.dict(),
        tenant_id=authenticated_entity.tenant_id,
        created_by=authenticated_entity.email,
    )

    if not new_rule.name or not new_rule.matchers:
        raise HTTPException(
            status_code=400, detail="Rule name and matchers are required"
        )

    session.add(new_rule)
    session.commit()
    session.refresh(new_rule)
    logger.info("Created a new mapping rule", extra={"rule_id": new_rule.id})
    return new_rule


@router.delete("/{rule_id}", description="Delete a mapping rule")
def delete_rule(
    rule_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:rules"])
    ),
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


@router.put("/{rule_id}", description="Update an existing rule")
def update_rule(
    rule_id: int,
    rule: MappingRuleUpdateDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:rules"])
    ),
    session: Session = Depends(get_session),
) -> MappingRuleDtoOut:
    logger.info("Updating a mapping rule")
    existing_rule: MappingRule = (
        session.query(MappingRule)
        .filter(
            MappingRule.tenant_id == authenticated_entity.tenant_id,
            MappingRule.id == rule_id,
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
    existing_rule.updated_by = authenticated_entity.email
    existing_rule.last_updated_at = datetime.datetime.now(tz=datetime.timezone.utc)
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


# todo: we can make it generic for all enrichment events, not only mapping
@router.get("/{rule_id}/executions", description="Get all executions for a rule")
def get_enrichment_events(
    rule_id: int,
    limit: int = Query(20),
    offset: int = Query(0),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:rules"])
    ),
) -> EnrichmentEventPaginatedResultsDto:
    logger.info(
        "Getting enrichment events",
        extra={
            "rule_id": rule_id,
            "limit": limit,
            "offset": offset,
            "tenant_id": authenticated_entity.tenant_id,
        },
    )
    enrichment_bl = EnrichmentsBl(tenant_id=authenticated_entity.tenant_id)
    events = enrichment_bl.get_enrichment_events(rule_id, limit, offset)
    total_count = enrichment_bl.get_total_enrichment_events(rule_id)
    logger.info(
        "Got enrichment events",
        extra={"events_count": len(events)},
    )
    return EnrichmentEventPaginatedResultsDto(
        count=total_count,
        items=events,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{rule_id}/executions/{enrichment_event_id}",
    description="Get an execution for a rule",
)
def get_enrichment_event_logs(
    rule_id: int,
    enrichment_event_id: UUID,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:rules"])
    ),
) -> EnrichmentEventWithLogs:
    logger.info(
        "Getting enrichment event logs",
        extra={
            "rule_id": rule_id,
            "enrichment_event_id": enrichment_event_id,
            "tenant_id": authenticated_entity.tenant_id,
        },
    )
    enrichment_bl = EnrichmentsBl(tenant_id=authenticated_entity.tenant_id)
    enrichment_event = enrichment_bl.get_enrichment_event(enrichment_event_id)
    logs = enrichment_bl.get_enrichment_event_logs(enrichment_event_id)
    if not logs:
        raise HTTPException(status_code=404, detail="Logs not found")
    logger.info(
        "Got enrichment event logs",
        extra={"logs_count": len(logs)},
    )
    return EnrichmentEventWithLogs(
        enrichment_event=enrichment_event,
        logs=logs,
    )


@router.post(
    "/{rule_id}/execute/{alert_id}",
    description="Execute a mapping rule against an alert",
    responses={
        200: {"description": "Mapping rule executed successfully"},
        400: {"description": "Mapping rule failed to execute"},
        404: {"description": "Mapping rule or alert not found"},
        403: {"description": "User does not have permission to execute mapping rule"},
    },
)
def execute_rule(
    rule_id: int,
    alert_id: UUID,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:rules"])
    ),
):
    logger.info(
        "Executing a mapping rule against an alert",
        extra={
            "rule_id": rule_id,
            "alert_id": alert_id,
            "tenant_id": authenticated_entity.tenant_id,
        },
    )
    enrichment_bl = EnrichmentsBl(tenant_id=authenticated_entity.tenant_id)
    enriched = enrichment_bl.run_mapping_rule_by_id(rule_id, alert_id)
    if enriched:
        logger.info(
            "Mapping rule executed successfully",
            extra={"rule_id": rule_id, "alert_id": alert_id},
        )
    else:
        logger.error(
            "Mapping rule failed to execute",
            extra={"rule_id": rule_id, "alert_id": alert_id},
        )
    return JSONResponse(
        status_code=200,
        content={"enrichment_event_id": str(enrichment_bl.enrichment_event_id)},
    )
