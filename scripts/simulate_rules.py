import logging
import os
import sys

from keep.api.core.db import create_rule, get_api_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

keep_api_key = os.environ.get("KEEP_API_KEY")
keep_api_url = os.environ.get("KEEP_API_URL")


def validate_env_vars():
    if not keep_api_key:
        logger.error("KEEP_API_KEY is missing. Please set it in the environment.")
        sys.exit(1)
    if not keep_api_url:
        logger.error("KEEP_API_URL is missing. Please set it in the environment.")
        sys.exit(1)


def create_rule_in_db(tenant_id, name, timeframe, definition, definition_cel, created_by, grouping_criteria=None, group_description=None):
    try:
        create_rule(
            tenant_id=tenant_id,
            name=name,
            timeframe=timeframe,
            definition=definition,
            definition_cel=definition_cel,
            created_by=created_by,
            grouping_criteria=grouping_criteria,
            group_description=group_description,
        )
        logger.info(f"Rule '{name}' inserted successfully.")
    except Exception as e:
        logger.error(f"Failed to create rule '{name}': {e}")
        sys.exit(1)


def simulate_rules():
    # Define the tenant ID
    logger.info("Inserting Rules")
    tenant_id = get_api_key(keep_api_key).tenant_id
    created_by = "keep"
    
    # Rule configurations
    rules = [
        {
            "name": "CPU (group by labels.instance)",
            "timeframe": 600,
            "definition": '{"sql": "((labels.alertname like :labels.alertname_1))", "params": {"labels.alertname_1": "%cpu%"}}',
            "definition_cel": '(labels.alertname.contains("cpu"))',
            "grouping_criteria": ["labels.instance"],
            "group_description": "CPU usage exceeded on {{ group_attributes.num_of_alerts }} pods of {{ labels.instance }} || {{ group_attributes.start_time }} | {{ group_attributes.last_update_time }}"
        },
        {
            "name": "CPU (no grouping)",
            "timeframe": 600,
            "definition": '{"sql": "((labels.alertname like :labels.alertname_1))", "params": {"labels.alertname_1": "%cpu%"}}',
            "definition_cel": '(labels.alertname.contains("cpu"))',
        },
        {
            "name": "MQ (group by labels.queue)",
            "timeframe": 600,
            "definition": '{"sql": "((name = :name_1))", "params": {"name_1": "mq_third_full"}}',
            "definition_cel": '(name == "mq_third_full")',
            "grouping_criteria": ["labels.queue"],
            "group_description": "The {{ labels.queue }} is more than third full on {{ group_attributes.num_of_alerts }} queue managers | {{ group_attributes.start_time }} || {{ group_attributes.last_update_time }}"
        }
    ]

    for rule in rules:
        create_rule_in_db(
            tenant_id=tenant_id,
            name=rule["name"],
            timeframe=rule["timeframe"],
            definition=rule["definition"],
            definition_cel=rule["definition_cel"],
            created_by=created_by,
            grouping_criteria=rule.get("grouping_criteria"),
            group_description=rule.get("group_description")
        )

    logger.info("All rules inserted successfully.")


if __name__ == "__main__":
    validate_env_vars()
    simulate_rules()
