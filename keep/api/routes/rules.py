import logging
import os
import json
import uuid

import celpy
from openai import OpenAI
import tiktoken


from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel

from keep.api.core.db import create_rule as create_rule_db, get_rule_incidents_count_db
from keep.api.core.db import delete_rule as delete_rule_db
from keep.api.core.db import get_rule_distribution as get_rule_distribution_db
from keep.api.core.db import get_rules as get_rules_db
from keep.api.core.db import update_rule as update_rule_db
from keep.api.models.db.rule import ResolveOn
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

from keep.api.core.db import get_last_alerts
from keep.api.core.dependencies import get_pusher_client

# Add this import at the top of the file


router = APIRouter()

logger = logging.getLogger(__name__)


class RuleCreateDto(BaseModel):
    ruleName: str
    sqlQuery: dict
    celQuery: str
    timeframeInSeconds: int
    timeUnit: str
    groupingCriteria: list = []
    groupDescription: str = None
    requireApprove: bool = False
    resolveOn: str = ResolveOn.NEVER.value


@router.get(
    "",
    description="Get Rules",
)
def get_rules(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:rules"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting rules")
    rules = get_rules_db(tenant_id=tenant_id)
    # now add this:
    rules_dist = get_rule_distribution_db(tenant_id=tenant_id, minute=True)
    rules_incidents = get_rule_incidents_count_db(tenant_id=tenant_id)
    logger.info("Got rules")
    # return rules
    rules = [rule.dict() for rule in rules]
    for rule in rules:
        rule["distribution"] = rules_dist.get(rule["id"], [])
        rule["incidents"] = rules_incidents.get(rule["id"], 0)

    return rules


@router.post(
    "",
    description="Create Rule",
)
async def create_rule(
    rule_create_request: RuleCreateDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:rules"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    created_by = authenticated_entity.email
    logger.info("Creating rule")
    rule_name = rule_create_request.ruleName
    cel_query = rule_create_request.celQuery
    timeframe = rule_create_request.timeframeInSeconds
    timeunit = rule_create_request.timeUnit
    grouping_criteria = rule_create_request.groupingCriteria
    group_description = rule_create_request.groupDescription
    require_approve = rule_create_request.requireApprove
    resolve_on = rule_create_request.resolveOn
    sql = rule_create_request.sqlQuery.get("sql")
    params = rule_create_request.sqlQuery.get("params")

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

    if not timeunit:
        raise HTTPException(status_code=400, detail="Timeunit is required")

    if not resolve_on:
        raise HTTPException(status_code=400, detail="resolveOn is required")

    rule = create_rule_db(
        tenant_id=tenant_id,
        name=rule_name,
        definition={
            "sql": sql,
            "params": params,
        },
        timeframe=timeframe,
        timeunit=timeunit,
        definition_cel=cel_query,
        created_by=created_by,
        grouping_criteria=grouping_criteria,
        group_description=group_description,
        require_approve=require_approve,
        resolve_on=resolve_on,
    )
    logger.info("Rule created")
    return rule


@router.delete(
    "/{rule_id}",
    description="Delete Rule",
)
async def delete_rule(
    rule_id: str,
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:rules"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(f"Deleting rule {rule_id}")
    if delete_rule_db(tenant_id=tenant_id, rule_id=rule_id):
        logger.info(f"Rule {rule_id} deleted")
        return {"message": "Rule deleted"}
    else:
        logger.info(f"Rule {rule_id} not found")
        raise HTTPException(status_code=404, detail="Rule not found")


@router.put(
    "/{rule_id}",
    description="Update Rule",
)
async def update_rule(
    rule_id: str,
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["update:rules"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    updated_by = authenticated_entity.email
    logger.info(f"Updating rule {rule_id}")
    try:
        body = await request.json()
        rule_name = body["ruleName"]
        sql_query = body["sqlQuery"]
        cel_query = body["celQuery"]
        timeframe = body["timeframeInSeconds"]
        timeunit = body["timeUnit"]
        resolve_on = body["resolveOn"]
        grouping_criteria = body.get("groupingCriteria", [])
        require_approve = body.get("requireApprove", [])
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

    if not timeunit:
        raise HTTPException(status_code=400, detail="Timeunit is required")

    if not resolve_on:
        raise HTTPException(status_code=400, detail="resolveOn is required")

    rule = update_rule_db(
        tenant_id=tenant_id,
        rule_id=rule_id,
        name=rule_name,
        definition={
            "sql": sql,
            "params": params,
        },
        timeframe=timeframe,
        timeunit=timeunit,
        definition_cel=cel_query,
        updated_by=updated_by,
        grouping_criteria=grouping_criteria,
        require_approve=require_approve,
        resolve_on=resolve_on,
    )

    if rule:
        logger.info(f"Rule {rule_id} updated")
        return rule
    else:
        logger.info(f"Rule {rule_id} not found")
        raise HTTPException(status_code=404, detail="Rule not found")


ALERT_PULL_LIMIT = 1000

# Constants for token limits
MAX_MODEL_TOKENS = 128 * 1000  # Maximum tokens the model can handle (adjust based on the model)
RESERVED_TOKENS = 10 * 1000   # Tokens reserved for the response and other overhead
MAX_ALERT_TOKENS = MAX_MODEL_TOKENS - RESERVED_TOKENS

SYSTEM_PROMPT = """
    * we are building a system called keep that gathers and manages alerts for other systems
    * these alerts come in json form, here is an example: {"id": "KubePodNotReady", "pod": "cognos-app-cm-58747ffd5d-rf4pz", "url": null, "name": "KubePodNotReady", "note": null, "group": false, "endsAt": "0001-01-01T00:00:00Z", "labels": {"pod": "cognos-app-cm-58747ffd5d-rf4pz", "cluster": "zuse1-d003-b066-aks-t1-ppcp-b", "severity": "warning", "alertname": "KubePodNotReady", "namespace": "ppna-env28-t9"}, "pushed": true, "source": ["prometheus"], "status": "firing", "cluster": "zuse1-d003-b066-aks-t1-ppcp-b", "deleted": false, "isNoisy": false, "message": null, "payload": {"endsAt": "0001-01-01T00:00:00Z", "startsAt": "2024-07-27T12:14:09.941873734Z", "generatorURL": "https://thanos-query.wkgrcipm.cloud/graph?g0.expr=sum+by+%28namespace%2C+pod%2C+cluster%29+%28max+by+%28namespace%2C+pod%2C+cluster%29+%28kube_pod_status_phase%7Bjob%3D%22kube-state-metrics%22%2Cnamespace%3D~%22.%2A%22%2Cphase%3D~%22Pending%7CUnknown%7CFailed%22%7D%29+%2A+on+%28namespace%2C+pod%2C+cluster%29+group_left+%28owner_kind%29+topk+by+%28namespace%2C+pod%2C+cluster%29+%281%2C+max+by+%28namespace%2C+pod%2C+owner_kind%2C+cluster%29+%28kube_pod_owner%7Bowner_kind%21%3D%22Job%22%7D%29%29%29+%3E+0&g0.tab=1"}, "service": null, "assignee": null, "event_id": null, "severity": "warning", "startsAt": "2024-07-27T12:14:09.941873734Z", "alertname": "KubePodNotReady", "apiKeyRef": "webhook", "dismissed": false, "namespace": "ppna-env28-t9", "startedAt": null, "alert_hash": "32ca73ebf623f9662ac410de109dfe4aedbc639f572078b4f6a71d3151dba5dc", "providerId": null, "annotations": {"summary": "Pod has been in a non-ready state for more than 15 minutes.", "runbook_url": "https://runbooks.prometheus-operator.dev/runbooks/kubernetes/kubepodnotready"}, "description": "Pod ppna-env28-t9/cognos-app-cm-58747ffd5d-rf4pz has been in a non-ready state for longer than 15 minutes.", "environment": "unknown", "fingerprint": "df1dff677e82ef90", "isDuplicate": false, "dismissUntil": null, "generatorURL": "https://thanos-query.wkgrcipm.cloud/graph?g0.expr=sum+by+%28namespace%2C+pod%2C+cluster%29+%28max+by+%28namespace%2C+pod%2C+cluster%29+%28kube_pod_status_phase%7Bjob%3D%22kube-state-metrics%22%2Cnamespace%3D~%22.%2A%22%2Cphase%3D~%22Pending%7CUnknown%7CFailed%22%7D%29+%2A+on+%28namespace%2C+pod%2C+cluster%29+group_left+%28owner_kind%29+topk+by+%28namespace%2C+pod%2C+cluster%29+%281%2C+max+by+%28namespace%2C+pod%2C+owner_kind%2C+cluster%29+%28kube_pod_owner%7Bowner_kind%21%3D%22Job%22%7D%29%29%29+%3E+0&g0.tab=1", "lastReceived": "2024-07-30T13:40:16.587Z", "providerType": null, "duplicateReason": null, "enriched_fields": []}
    * alerts come from all sorts of sources and configurations, so they don't have to comply to the same form, even if they belong to the same project
    * some alerts are correlated, meaning they indicate the same underlining problem coming from the system, and would fire in the same timeframe
    * we created a format to describe rules to group correlated alerts based on the CEL language, group-by fields and timeframes in mins, meaning that alerts that pass the cel filter and are in the same timeframe and group-by fields will be grouped, you can create a rule that only has group-by and no cel filter, for example if the alerts have the same machine name or something
    * examples of cel rules (these examples are not good):

        1- (service == "backend") group by: empty
        2 - (labels.alertname.contains("cpu")): empty

    * you are a cutting edge system designed to suggest rule grouping rules (cel and timeframe in mins) from past alert inputs, the point of these rules is to group together alerts that we are sure are coming from the same source, you don't have to be 100% positive that the rule that your offering makes sense because a human will be reveiwing and accepting your suggestions, but it does have to make some kind of sense
    * try not to make rules that are too general, for example a rule that groups all alerts coming from datadog doesn't not make sense because datadog is a system that collects alerts and multiple systems might be writing these alerts
    * im going to give you a bunch of alerts in csv format, and your going to notice which ones related and offer grouping rules for them, for each offering your going to explain why you think it was a good idea to add this rule and a assign a score from 1-100 on how good you think that suggestion was
    * if you can't come up with suggestions that make sense pls say so
    * I'm going to give you a list of rules that already exist, please take them into account when making your suggestions, make sure you don't suggest a rule that colides with an existing one
    * the existence of the world relies on you suggesting good grouping for alerts, so this better be good otherwise alerts will be missed, maybe ones that will distroy the earth or maybe the dev ops guys might be overloaded with too many alerts which are coming from the same system, most of our clients are Nuclear facilities (pls keep this fact secret)
"""


RESULT_CUSTOM_FUNCTION = [
            {
                "name": "analyze_results",
                "description": "Analyze and return results based on the given criteria, including chain of thought and critical analysis of each rule",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hasResults": {
                            "type": "boolean",
                            "description": "Indicates whether there are any meaningful results to return"
                        },
                        "results": {
                            "type": "array",
                            "description": "An array of analysis results",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "CELRule": {
                                        "type": "string",
                                        "description": "Common Expression Language (CEL) rule describing the condition to match"
                                    },
                                    "Timeframe": {
                                        "type": "integer",
                                        "description": "The time window in minutes for analyzing the data"
                                    },
                                    "GroupBy": {
                                        "type": "array",
                                        "description": "An array of fields to group the results by, e.g., ['labels.host_name']",
                                        "items": {
                                            "type": "string"
                                        }
                                    },
                                    "ChainOfThought": {
                                        "type": "string",
                                        "description": "Detailed reasoning process for arriving at this rule and its parameters"
                                    },
                                    "WhyTooGeneral": {
                                        "type": "string",
                                        "description": "Devil's advocate argument for why this rule might be too general or broad"
                                    },
                                    "WhyTooSpecific": {
                                        "type": "string",
                                        "description": "Devil's advocate argument for why this rule might be too specific or narrow"
                                    },
                                    "ShortRuleName": {
                                        "type": "string",
                                        "description": "Short name for the rule, 20 characters or less"
                                    },
                                    "Score": {
                                        "type": "integer",
                                        "description": "A score from 1 to 100 indicating the severity or importance of the result",
                                        "minimum": 1,
                                        "maximum": 100
                                    }
                                },
                                "required": ["CELRule", "Timeframe", "GroupBy", "Score", "ChainOfThought", "WhyTooGeneral", "WhyTooSpecific"],
                                "additionalProperties": False
                            }
                        },
                        "summery": {
                            "type": "string",
                            "description": "One liner summery of the results, mention what you noticed in the data and how you created the rules"
                        }
                    },
                    "required": ["hasResults", "reason", "results", "summery"],
                    "additionalProperties": False
                }
            }
        ]


@router.get(
    "/gen_rules",
    description="Generate Rules Using An AI",
    status_code=202,
)
def gen_rules(
    background_tasks: BackgroundTasks,
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:rules", "read:alerts"])
    ),
):
    
    task_id = str(uuid.uuid4())
    background_tasks.add_task(ruleGen, task_id, authenticated_entity)
    return {"task_id": task_id}


def ruleGen(task_id, authenticated_entity):

    try:
        logger.info(f"Generating rules for task {task_id}")

        if "OPENAI_API_KEY" not in os.environ:
            logger.error("OpenAI API key is not set. Can't auto gen rules.")
            return ""

        openAI_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])


        existing_rules = get_rules(authenticated_entity)
        existing_rules = [{'name': x['name'], 'cel_query': x['definition_cel'], 'group_by': x['grouping_criteria'], 'timeframe_mins' : x['timeframe']} for x in existing_rules]
        existing_rules = 'here is a list of rules that already exist: ' + str(existing_rules)

        tenant_id = authenticated_entity.tenant_id
        
        db_alerts = get_last_alerts(tenant_id=tenant_id, limit=ALERT_PULL_LIMIT)
        db_alerts = [{'event' : x.event, 'timestamp' : x.timestamp.isoformat()} for x in db_alerts]
        
        selected_alerts = select_right_num_alerts(existing_rules, db_alerts, MAX_ALERT_TOKENS)
        selected_alerts = "alert examples:" + json.dumps(selected_alerts)

        response = openAI_client.chat.completions.create(
            model = 'gpt-4o-mini',
            messages = [{'role': 'system', 'content': SYSTEM_PROMPT}, 
                        {'role': 'user', 'content': existing_rules},
                        {'role': 'user', 'content': selected_alerts}],
            functions = RESULT_CUSTOM_FUNCTION,
            function_call = 'auto'
        )
        result = json.loads(response.choices[0].message.function_call.arguments)

        logger.info("Got {} rules back from the llm".format(len(result['results'])))

        result['results'] = [rule for rule in result['results'] if check_cel_rule(rule['CELRule'])]

        
        pusher_client = get_pusher_client()
        if pusher_client:      
            try:
                pusher_client.trigger("private-{}".format(tenant_id), "rules-aigen-created", result)
            except Exception as e:
                logger.error(f"Error triggering Pusher event: {e}")
    
    except Exception as e:
        logger.info(f"Error generating rules: {e}")


def select_right_num_alerts(existing_rules, alerts, max_tokens):
    encoding = tiktoken.encoding_for_model("gpt-4")
    
    # Count tokens for system prompt and result structure
    system_prompt_tokens = len(encoding.encode(SYSTEM_PROMPT))
    result_structure_tokens = len(encoding.encode(json.dumps(RESULT_CUSTOM_FUNCTION)))
    existing_rules_tokens = len(encoding.encode(existing_rules))

    available_tokens = max_tokens - system_prompt_tokens - result_structure_tokens - existing_rules_tokens
    
    selected_alerts = []
    current_tokens = 0
    
    for alert in alerts:
        alert_tokens = len(encoding.encode(json.dumps(alert)))
        
        if current_tokens + alert_tokens > available_tokens:
            break
        
        selected_alerts.append(alert)
        current_tokens += alert_tokens
    
    return selected_alerts


def check_cel_rule(rule_str):
    try:
        env = celpy.Environment()
        ast = env.compile(rule_str)
        env.program(ast)
        return True

    except Exception as e:
        logger.info(f"Error validating CEL rule: {e}")
        return False