import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from keep.api.core.db import create_rule as create_rule_db
from keep.api.core.db import get_rules as get_rules_db
from keep.api.core.dependencies import (
    get_user_email,
    verify_bearer_token,
    verify_token_or_key,
)

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get Rules",
)
def get_rules(
    tenant_id: str = Depends(verify_bearer_token),
):
    logger.info("Getting rules")
    rules = get_rules_db(tenant_id=tenant_id)
    logger.info("Got rules")
    # return rules
    return rules


@router.post(
    "",
    description="Create Rule",
)
async def create_rule(
    request: Request,
    tenant_id: str = Depends(verify_token_or_key),
    created_by: str = Depends(get_user_email),
):
    logger.info("Creating rule")
    try:
        body = await request.json()
        rule_name = body["ruleName"]
        sql_query = body["sqlQuery"]
        cel_query = body["celQuery"]
        timeframe = body["timeframeInSeconds"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    sql = sql_query.get("sql")
    params = sql_query.get("params")

    if not sql:
        raise HTTPException(status_code=400, detail="SQL is required")

    if not params:
        raise HTTPException(status_code=400, detail="Params are required")

    if not cel_query:
        raise HTTPException(status_code=400, detail="CEL is required")

    if not rule_name:
        raise HTTPException(status_code=400, detail="Rule name is required")

    if not timeframe:
        raise HTTPException(status_code=400, detail="Timeframe is required")

    rule = create_rule_db(
        tenant_id=tenant_id,
        name=rule_name,
        definition={
            "sql": sql,
            "params": params,
        },
        timeframe=timeframe,
        definition_cel=cel_query,
        created_by=created_by,
    )
    logger.info("Rule created")
    return rule
