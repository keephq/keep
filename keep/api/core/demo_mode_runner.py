import os
import requests
import asyncio
import logging
import threading
import random
import time
import datetime
from datetime import timezone

from keep.api.core.db import get_session_sync
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.utils.tenant_utils import get_or_create_api_key
from keep.providers.providers_factory import ProvidersFactory

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

LIVE_DEMO_MODE = os.environ.get("LIVE_DEMO_MODE", "false").lower() == "true"

correlation_rules_to_create = [
    {
        "sqlQuery": {
            "sql": "((name like :name_1))",
            "params": {
                "name_1": "%mq%"
            }
        },
        "groupDescription": "This rule groups all alerts related to MQ.",
        "ruleName": "Message Queue Buckle Up",
        "celQuery": "(name.contains(\"mq\"))",
        "timeframeInSeconds": 86400,
        "timeUnit": "hours",
        "groupingCriteria": [],
        "requireApprove": False,
        "resolveOn": "never"
    },
    {
        "sqlQuery": {
            "sql": "((name like :name_1) or (name = :name_2) or (name like :name_3))",
            "params": {
                "name_1": "%network_latency_high%",
                "name_2": "high_cpu_usage",
                "name_3": "%database_connection_failure%"
            }
        },
        "groupDescription": "This rule groups alerts from multiple sources.",
        "ruleName": "Application issue caused by DB load",
        "celQuery": "(name.contains(\"network_latency_high\")) || (name == \"high_cpu_usage\") || (name.contains(\"database_connection_failure\"))",
        "timeframeInSeconds": 86400,
        "timeUnit": "hours",
        "groupingCriteria": [],
        "requireApprove": False,
        "resolveOn": "never"
    },
]


def get_or_create_correlation_rules(keep_api_key, keep_api_url):
    correlation_rules_existing = requests.get(
        f"{keep_api_url}/rules",
        headers={"x-api-key": keep_api_key},
    )
    correlation_rules_existing.raise_for_status()
    correlation_rules_existing = correlation_rules_existing.json()

    if len(correlation_rules_existing) == 0:
        for correlation_rule in correlation_rules_to_create:
            response = requests.post(
                f"{keep_api_url}/rules",
                headers={"x-api-key": keep_api_key},
                json=correlation_rule,
            )
            response.raise_for_status()


def remove_old_incidents(keep_api_key, keep_api_url):
    consider_old_timedelta = datetime.timedelta(minutes=30)
    incidents_existing = requests.get(
        f"{keep_api_url}/incidents",
        headers={"x-api-key": keep_api_key},
    )
    incidents_existing.raise_for_status()
    incidents_existing = incidents_existing.json()['items']

    for incident in incidents_existing:
        if datetime.datetime.strptime(
                incident["creation_time"], "%Y-%m-%dT%H:%M:%S.%f"
        ).replace(tzinfo=timezone.utc) < (datetime.datetime.now() - consider_old_timedelta).astimezone(timezone.utc):
            incident_id = incident["id"]
            response = requests.delete(
                f"{keep_api_url}/incidents/{incident_id}",
                headers={"x-api-key": keep_api_key},
            )
            response.raise_for_status()


async def simulate_alerts(keep_api_url=None, keep_api_key=None, sleep_interval=5, demo_correlation_rules=False):
    GENERATE_DEDUPLICATIONS = True

    providers = ["prometheus", "grafana"]

    provider_classes = {
        provider: ProvidersFactory.get_provider_class(provider)
        for provider in providers
    }

    # Wait in the beginning because server may not be ready yet.
    await asyncio.sleep(sleep_interval * 2)

    get_or_create_correlation_rules(keep_api_key, keep_api_url)

    while True:
        await asyncio.sleep(sleep_interval)

        remove_old_incidents(keep_api_key, keep_api_url)

        # choose provider
        provider_type = random.choice(providers)
        send_alert_url = "{}/alerts/event/{}".format(
            keep_api_url, provider_type)
        provider = provider_classes[provider_type]
        alert = provider.simulate_alert()

        # Determine number of times to send the same alert
        num_iterations = 1
        if GENERATE_DEDUPLICATIONS:
            num_iterations = random.randint(1, 3)

        for _ in range(num_iterations):
            logger.info("Sending alert: {}".format(alert))
            try:
                env = random.choice(["production", "staging", "development"])
                response = requests.post(
                    send_alert_url + f"?provider_id={provider_type}-{env}",
                    headers={"x-api-key": keep_api_key},
                    json=alert,
                )
                response.raise_for_status()  # Raise an HTTPError for bad responses
            except requests.exceptions.RequestException as e:
                logger.error("Failed to send alert: {}".format(e))
                time.sleep(sleep_interval)
                continue

            if response.status_code != 202:
                logger.error("Failed to send alert: {}".format(response.text))
            else:
                logger.info("Alert sent successfully")

def launch_demo_mode():
    """
    Running async demo in the backgound.
    """
    keep_api_url = "http://localhost:" + str(os.environ.get("PORT", 8080))
    keep_api_key = os.environ.get("KEEP_API_KEY", get_or_create_api_key(
        session=get_session_sync(),
        tenant_id=SINGLE_TENANT_UUID,
        created_by="system",
        unique_api_key_id="simulate_alerts",
        system_description="Simulate Alerts API key",
    ))

    if LIVE_DEMO_MODE:
        thread = threading.Thread(target=asyncio.run, args=(simulate_alerts(
            keep_api_url,
            keep_api_key, 
            sleep_interval=5, 
            demo_correlation_rules=True
        ), ))
        thread.start()
        logger.info("Simulate Alert launched.")
    else:
        logger.info("Alert simulation is disabled.")
