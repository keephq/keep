import json
import logging
import re

import celpy

import keep.api.core.db as db
from keep.api.core.config import config
from keep.api.models.db.rule import CreateIncidentOn, ResolveOn

logger = logging.getLogger(__name__)

KEEP_CORRELATION_RULES_ENV_VAR = "KEEP_CORRELATION_RULES"
SYSTEM_ACTOR = "system"

_REQUIRED_FIELDS = ("ruleName", "celQuery", "sqlQuery", "timeframeInSeconds", "timeUnit")
_CEL_ENV = celpy.Environment()


def provision_correlation_rules_from_env(tenant_id: str):
    """Provision correlation (rules-engine) rules from ``KEEP_CORRELATION_RULES``.

    Mirrors ``provision_deduplication_rules_from_env``: the env var holds a JSON
    array (or a path to a ``.json`` file) of rule specs matching the ``POST /rules``
    schema. On every startup the DB is reconciled to the env:

      - Provisioned rules whose ``ruleName`` is no longer in the env are deleted.
      - A provisioned rule with a matching name is updated in place.
      - A new provisioned rule is created (``is_provisioned=True``).
      - UI-created rules (``is_provisioned=False``) are never touched.

    If the env var is unset, any currently-provisioned rules are deprovisioned.
    A spec that fails validation (missing field or an unparseable ``celQuery``)
    is logged and skipped so one bad rule does not block the others.
    """
    rules_to_provision = get_correlation_rules_to_provision()

    provisioned_rules = [rule for rule in db.get_rules(tenant_id) if rule.is_provisioned]

    if not rules_to_provision:
        if provisioned_rules:
            logger.info(
                "%s unset; deprovisioning %d existing correlation rule(s)",
                KEEP_CORRELATION_RULES_ENV_VAR,
                len(provisioned_rules),
            )
            for rule in provisioned_rules:
                db.delete_rule(tenant_id=tenant_id, rule_id=str(rule.id))
        else:
            logger.info(
                "No correlation rules to provision and none currently provisioned"
            )
        return

    provisioned_rules_by_name = {rule.name: rule for rule in provisioned_rules}

    # delete provisioned rules that are no longer in the env
    for rule in provisioned_rules:
        if str(rule.name) not in rules_to_provision:
            logger.info(
                "Correlation rule with name '%s' is not in the env, deleting from DB",
                rule.name,
            )
            db.delete_rule(tenant_id=tenant_id, rule_id=str(rule.id))

    for rule_name, rule_to_provision in rules_to_provision.items():
        try:
            _validate_rule_to_provision(rule_name, rule_to_provision)
        except ValueError as exc:
            logger.warning(
                "Skipping invalid correlation rule '%s': %s", rule_name, exc
            )
            continue

        existing_rule = provisioned_rules_by_name.get(rule_name)
        if existing_rule is not None:
            logger.info(
                "Correlation rule with name '%s' already exists, updating in DB",
                rule_name,
            )
            _update_correlation_rule(
                tenant_id, str(existing_rule.id), rule_name, rule_to_provision
            )
            continue

        logger.info(
            "Correlation rule with name '%s' does not exist, creating in DB",
            rule_name,
        )
        _create_correlation_rule(tenant_id, rule_name, rule_to_provision)


def get_correlation_rules_to_provision() -> dict[str, dict]:
    """Read correlation rules from ``KEEP_CORRELATION_RULES`` as a dict keyed by name.

    The env var is either an absolute/relative path to a ``.json`` file or a JSON
    string. Its content is a JSON array of rule specs matching the ``POST /rules``
    schema (a single object is also accepted). Specs without a ``ruleName`` are
    skipped.
    """
    rules_from_env_var = config(key=KEEP_CORRELATION_RULES_ENV_VAR, default=None)

    if not rules_from_env_var:
        return None

    if re.compile(r"^(\/|\.\/|\.\.\/).*\.json$").match(rules_from_env_var):
        with open(file=rules_from_env_var, mode="r", encoding="utf8") as file:
            try:
                parsed = json.loads(file.read())
            except json.JSONDecodeError as e:
                raise Exception(
                    f"Error parsing correlation rules from file {rules_from_env_var}: {e}"
                ) from e
    else:
        try:
            parsed = json.loads(rules_from_env_var)
        except json.JSONDecodeError as e:
            raise Exception(
                f"Error parsing correlation rules from env var {KEEP_CORRELATION_RULES_ENV_VAR}: {e}"
            ) from e

    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise Exception(
            f"{KEEP_CORRELATION_RULES_ENV_VAR} must be a JSON array of rule specs"
        )

    rules_dict: dict[str, dict] = {}
    for rule in parsed:
        if not isinstance(rule, dict):
            logger.warning("Skipping non-object correlation rule spec: %r", rule)
            continue
        rule_name = rule.get("ruleName")
        if not rule_name:
            logger.warning(
                "Skipping correlation rule spec without 'ruleName': %r", rule
            )
            continue
        rules_dict[rule_name] = rule

    return rules_dict or None


def _validate_rule_to_provision(rule_name: str, rule_to_provision: dict) -> None:
    for field in _REQUIRED_FIELDS:
        if not rule_to_provision.get(field):
            raise ValueError(f"missing required field '{field}'")

    sql_query = rule_to_provision.get("sqlQuery")
    if not isinstance(sql_query, dict) or not sql_query.get("sql"):
        raise ValueError("'sqlQuery.sql' is required")

    try:
        _CEL_ENV.compile(rule_to_provision["celQuery"])
    except Exception as exc:
        raise ValueError(f"unparseable celQuery: {exc}") from exc


def _create_correlation_rule(
    tenant_id: str, rule_name: str, rule_to_provision: dict
) -> None:
    sql_query = rule_to_provision["sqlQuery"]
    db.create_rule(
        tenant_id=tenant_id,
        name=rule_name,
        definition={"sql": sql_query.get("sql"), "params": sql_query.get("params")},
        timeframe=rule_to_provision["timeframeInSeconds"],
        timeunit=rule_to_provision["timeUnit"],
        definition_cel=rule_to_provision["celQuery"],
        created_by=SYSTEM_ACTOR,
        grouping_criteria=rule_to_provision.get("groupingCriteria", []),
        group_description=rule_to_provision.get("groupDescription"),
        require_approve=rule_to_provision.get("requireApprove", False),
        resolve_on=rule_to_provision.get("resolveOn", ResolveOn.NEVER.value),
        create_on=rule_to_provision.get("createOn", CreateIncidentOn.ANY.value),
        incident_name_template=rule_to_provision.get("incidentNameTemplate"),
        incident_prefix=rule_to_provision.get("incidentPrefix"),
        multi_level=rule_to_provision.get("multiLevel", False),
        multi_level_property_name=rule_to_provision.get("multiLevelPropertyName"),
        threshold=rule_to_provision.get("threshold", 1),
        assignee=rule_to_provision.get("assignee"),
        is_provisioned=True,
    )


def _update_correlation_rule(
    tenant_id: str, rule_id: str, rule_name: str, rule_to_provision: dict
) -> None:
    sql_query = rule_to_provision["sqlQuery"]
    db.update_rule(
        tenant_id=tenant_id,
        rule_id=rule_id,
        name=rule_name,
        definition={"sql": sql_query.get("sql"), "params": sql_query.get("params")},
        timeframe=rule_to_provision["timeframeInSeconds"],
        timeunit=rule_to_provision["timeUnit"],
        definition_cel=rule_to_provision["celQuery"],
        updated_by=SYSTEM_ACTOR,
        grouping_criteria=rule_to_provision.get("groupingCriteria", []),
        require_approve=rule_to_provision.get("requireApprove", False),
        resolve_on=rule_to_provision.get("resolveOn", ResolveOn.NEVER.value),
        create_on=rule_to_provision.get("createOn", CreateIncidentOn.ANY.value),
        incident_name_template=rule_to_provision.get("incidentNameTemplate"),
        incident_prefix=rule_to_provision.get("incidentPrefix"),
        multi_level=rule_to_provision.get("multiLevel", False),
        multi_level_property_name=rule_to_provision.get("multiLevelPropertyName"),
        threshold=rule_to_provision.get("threshold", 1),
        assignee=rule_to_provision.get("assignee"),
    )
