import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.db import get_alert_by_event_id, get_session
from keep.api.models.db.enrichment_event import EnrichmentEventWithLogs, EnrichmentType
from keep.api.models.db.extraction import (
    ExtractionRule,
    ExtractionRuleDtoBase,
    ExtractionRuleDtoOut,
)
from keep.api.utils.pagination import EnrichmentEventPaginatedResultsDto
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("", description="Get all extraction rules")
def get_extraction_rules(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:extraction"])
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
        IdentityManagerFactory.get_auth_verifier(["write:extraction"])
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
        IdentityManagerFactory.get_auth_verifier(["write:extraction"])
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
    session.commit()
    session.refresh(rule)
    return ExtractionRuleDtoOut(**rule.dict())


@router.delete("/{rule_id}", description="Delete an extraction rule")
def delete_extraction_rule(
    rule_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:extraction"])
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


@router.post(
    "/{rule_id}/execute/{alert_id}",
    description="Execute an extraction rule against an alert",
    responses={
        200: {"description": "Extraction rule executed successfully"},
        400: {"description": "Extraction rule failed to execute"},
        404: {"description": "Extraction rule or alert not found"},
        403: {
            "description": "User does not have permission to execute extraction rule"
        },
    },
)
def execute_rule(
    rule_id: int,
    alert_id: UUID,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:extraction"])
    ),
):
    logger.info(
        "Executing an extraction rule against an alert",
        extra={
            "rule_id": rule_id,
            "alert_id": alert_id,
            "tenant_id": authenticated_entity.tenant_id,
        },
    )
    enrichment_bl = EnrichmentsBl(tenant_id=authenticated_entity.tenant_id)
    alert = get_alert_by_event_id(authenticated_entity.tenant_id, str(alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    enriched = enrichment_bl.run_extraction_rule_by_id(rule_id, alert)
    if enriched:
        logger.info(
            "Extraction rule executed successfully",
            extra={"rule_id": rule_id, "alert_id": alert_id},
        )
    else:
        logger.error(
            "Extraction rule failed to execute",
            extra={"rule_id": rule_id, "alert_id": alert_id},
        )
    return JSONResponse(
        status_code=200,
        content={"enrichment_event_id": str(enrichment_bl.enrichment_event_id)},
    )


@router.get("/{rule_id}/executions", description="Get all executions for a rule")
def get_enrichment_events(
    rule_id: int,
    limit: int = Query(20),
    offset: int = Query(0),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:extraction"])
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
    events = enrichment_bl.get_enrichment_events(
        rule_id, limit, offset, EnrichmentType.EXTRACTION
    )
    total_count = enrichment_bl.get_total_enrichment_events(
        rule_id, EnrichmentType.EXTRACTION
    )
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
        IdentityManagerFactory.get_auth_verifier(["read:extraction"])
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
