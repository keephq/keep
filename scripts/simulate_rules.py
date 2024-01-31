# A script that simulates the creation of rules in the database
# Written for demonstration purposes only
import logging
import os

from keep.api.core.db import create_rule, get_api_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

keep_api_key = os.environ.get("KEEP_API_KEY")
keep_api_url = os.environ.get("KEEP_API_URL")


def simulate_rules():
    # Define the tenant ID
    logger.info("Inserting Rules")
    tenant_id = get_api_key(keep_api_key).tenant_id
    created_by = "keep"
    definition_template = '{{"sql": "((labels.alertname like :labels.alertname_1))", "params": {{"labels.alertname_1": "%cpu%"}}}}'
    definition_cel_template = '(labels.alertname.contains("cpu"))'
    timeframe = 600

    # Rule #1 - CPU (group by labels.instance)
    create_rule(
        tenant_id=tenant_id,
        name="CPU (group by labels.instance)",
        timeframe=timeframe,
        definition=definition_template,
        definition_cel=definition_cel_template,
        created_by=created_by,
        grouping_criteria=["labels.instance"],
        group_description="CPU usage exceeded on {{ group_attributes.num_of_alerts }} pods of {{ labels.instance }} || {{ group_attributes.start_time }} | {{ group_attributes.last_update_time }}",
    )

    # Rule #2 - CPU (no grouping)
    create_rule(
        tenant_id=tenant_id,
        name="CPU (no grouping)",
        timeframe=timeframe,
        definition=definition_template,
        definition_cel=definition_cel_template,
        created_by=created_by,
    )

    # Rule #3 - MQ (group by labels.queue)
    mq_definition_template = (
        '{{"sql": "((name = :name_1))", "params": {{"name_1": "mq_third_full"}}}}'
    )
    mq_definition_cel_template = '(name == "mq_third_full")'
    create_rule(
        tenant_id=tenant_id,
        name="MQ (group by labels.queue)",
        timeframe=timeframe,
        definition=mq_definition_template,
        definition_cel=mq_definition_cel_template,
        created_by=created_by,
        grouping_criteria=["labels.queue"],
        group_description="The {{ labels.queue }} is more than third full on {{ group_attributes.num_of_alerts }} queue managers | {{ group_attributes.start_time }} || {{ group_attributes.last_update_time }}",
    )
    logger.info("Rules inserted successfully")


if __name__ == "__main__":
    simulate_rules()
