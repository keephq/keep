import datetime
import logging
import os
import random
import threading
import time
from datetime import timezone
from uuid import uuid4

import requests
from dateutil import parser
from requests.models import PreparedRequest

from keep.api.core.db import get_session_sync
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.logging import CONFIG
from keep.api.models.db.topology import TopologyServiceInDto
from keep.api.tasks.process_topology_task import process_topology
from keep.api.utils.tenant_utils import get_or_create_api_key
from keep.providers.providers_factory import ProvidersFactory

logging.config.dictConfig(CONFIG)

logger = logging.getLogger(__name__)

KEEP_LIVE_DEMO_MODE = os.environ.get("KEEP_LIVE_DEMO_MODE", "false").lower() == "true"

correlation_rules_to_create = [
    {
        "sqlQuery": {"sql": "((name like :name_1))", "params": {"name_1": "%mq%"}},
        "groupDescription": "This rule groups all alerts related to MQ.",
        "ruleName": "Message queue is getting filled up",
        "celQuery": '(name.contains("mq"))',
        "timeframeInSeconds": 86400,
        "timeUnit": "hours",
        "groupingCriteria": [],
        "requireApprove": False,
        "resolveOn": "never",
    },
    {
        "sqlQuery": {
            "sql": "((name like :name_1) or (name = :name_2) or (name like :name_3))",
            "params": {
                "name_1": "%network_latency_high%",
                "name_2": "high_cpu_usage",
                "name_3": "%database_connection_failure%",
            },
        },
        "groupDescription": "This rule groups alerts from multiple sources.",
        "ruleName": "Application issue caused by DB load",
        "celQuery": '(name.contains("network_latency_high")) || (name == "high_cpu_usage") || (name.contains("database_connection_failure"))',
        "timeframeInSeconds": 86400,
        "timeUnit": "hours",
        "groupingCriteria": [],
        "requireApprove": False,
        "resolveOn": "never",
    },
]

services_to_create = [
    TopologyServiceInDto(
        source_provider_id="Prod-Datadog",
        repository="keephq/keep",
        tags=[],
        service="api",
        display_name="API Service",
        environment="prod",
        description="The main API service",
        team="keep",
        email="support@keephq.dev",
        slack="https://slack.keephq.dev",
        ip_address="10.0.0.1",
        category="Python",
        manufacturer="",
        dependencies={
            "db": "SQL",
            "queue": "AMQP",
        },
        application_ids=[],
        updated_at="2024-11-18T09:23:46",
    ),
    TopologyServiceInDto(
        source_provider_id="Prod-Datadog",
        repository="keephq/keep",
        tags=[],
        service="ui",
        display_name="Platform",
        environment="prod",
        description="The user interface (aka Platform)",
        team="keep",
        email="support@keephq.dev",
        slack="https://slack.keephq.dev",
        ip_address="10.0.0.2",
        category="nextjs",
        manufacturer="",
        dependencies={
            "api": "HTTP/S",
        },
        application_ids=[],
        updated_at="2024-11-18T09:29:25",
    ),
    TopologyServiceInDto(
        source_provider_id="Prod-Datadog",
        repository="keephq/keep",
        tags=[],
        service="db",
        display_name="DB",
        environment="prod",
        description="Production Database",
        team="keep",
        email="support@keephq.dev",
        slack="https://slack.keephq.dev",
        ip_address="10.0.0.3",
        category="postgres",
        manufacturer="",
        dependencies={},
        application_ids=[],
        updated_at="2024-11-18T09:30:44",
    ),
    TopologyServiceInDto(
        source_provider_id="Prod-Datadog",
        repository="keephq/keep",
        tags=[],
        service="queue",
        display_name="Kafka",
        environment="prod",
        description="Production Queue",
        team="keep",
        email="support@keephq.dev",
        slack="https://slack.keephq.dev",
        ip_address="10.0.0.4",
        category="Kafka",
        dependencies={
            "processor": "AMQP",
        },
        application_ids=[],
        updated_at="2024-11-18T09:31:31",
    ),
    TopologyServiceInDto(
        source_provider_id="Prod-Datadog",
        repository="keephq/keep",
        tags=[],
        service="processor",
        display_name="Processor",
        environment="prod",
        description="Processing Service",
        team="keep",
        email="support@keephq.dev",
        slack="https://slack.keephq.dev",
        ip_address="10.0.0.5",
        category="go",
        dependencies={
            "storage": "HTTP/S",
        },
        application_ids=[],
        updated_at="2024-11-18T10:02:20",
    ),
    TopologyServiceInDto(
        source_provider_id="Prod-Datadog",
        repository="keephq/keep",
        tags=[],
        service="backoffice",
        display_name="Backoffice",
        environment="prod",
        description="Backoffice UI to control configuration",
        team="keep",
        email="support@keephq.dev",
        slack="https://slack.keephq.dev",
        ip_address="172.1.1.0",
        category="nextjs",
        dependencies={
            "api": "HTTP/S",
        },
        application_ids=[],
        updated_at="2024-11-18T10:11:31",
    ),
    TopologyServiceInDto(
        source_provider_id="Prod-Datadog",
        repository="keephq/keep",
        tags=[],
        service="storage",
        display_name="Storage",
        environment="prod",
        description="Storage Service",
        team="keep",
        email="support@keephq.dev",
        slack="https://slack.keephq.dev",
        ip_address="10.0.0.8",
        category="python",
        dependencies={},
        application_ids=[],
        updated_at="2024-11-18T10:13:56",
    ),
]

application_to_create = {
    "name": "Main App",
    "description": "It is the most critical business process ever imaginable.",
    "services": [
        {"name": "API Service", "service": "api"},
        {"name": "DB", "service": "db"},
        {"name": "Kafka", "service": "queue"},
        {"name": "Processor", "service": "processor"},
        {"name": "Storage", "service": "storage"},
    ],
}


def get_or_create_topology(keep_api_key, keep_api_url):
    services_existing = requests.get(
        f"{keep_api_url}/topology",
        headers={"x-api-key": keep_api_key},
    )
    services_existing.raise_for_status()
    services_existing = services_existing.json()

    # Creating services
    if len(services_existing) == 0:
        process_topology(
            SINGLE_TENANT_UUID, services_to_create, "Prod-Datadog", "datadog"
        )

        # Create application
        applications_existing = requests.get(
            f"{keep_api_url}/topology/applications",
            headers={"x-api-key": keep_api_key},
        )
        applications_existing.raise_for_status()
        applications_existing = applications_existing.json()

        if len(applications_existing) == 0:
            # Pull services again to get their ids
            services_existing = requests.get(
                f"{keep_api_url}/topology",
                headers={"x-api-key": keep_api_key},
            )
            services_existing.raise_for_status()
            services_existing = services_existing.json()

            # Update application_to_create with existing services ids
            for service in application_to_create["services"]:
                for existing_service in services_existing:
                    if service["name"] == existing_service["display_name"]:
                        service["id"] = existing_service["id"]

            # Check if any service does not have an id
            for service in application_to_create["services"]:
                if "id" not in service:
                    logger.error(
                        f"Service {service['name']} does not have an id. Application creation failed."
                    )
                    return True

            response = requests.post(
                f"{keep_api_url}/topology/applications",
                headers={"x-api-key": keep_api_key},
                json=application_to_create,
            )
            response.raise_for_status()


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
    incidents_existing = incidents_existing.json()["items"]

    for incident in incidents_existing:
        if parser.parse(incident["creation_time"]).replace(tzinfo=timezone.utc) < (
            datetime.datetime.now() - consider_old_timedelta
        ).astimezone(timezone.utc):
            incident_id = incident["id"]
            response = requests.delete(
                f"{keep_api_url}/incidents/{incident_id}",
                headers={"x-api-key": keep_api_key},
            )
            response.raise_for_status()


def get_installed_providers(keep_api_key, keep_api_url):
    response = requests.get(
        f"{keep_api_url}/providers",
        headers={"x-api-key": keep_api_key},
    )
    response.raise_for_status()
    return response.json()["installed_providers"]


def simulate_alerts(
    keep_api_url=None,
    keep_api_key=None,
    sleep_interval=5,
    demo_correlation_rules=False,
    demo_topology=False,
    clean_old_incidents=False,
):
    logger.info("Simulating alerts...")

    GENERATE_DEDUPLICATIONS = False

    providers = [
        "prometheus",
        "grafana",
        "cloudwatch",
        "datadog",
    ]

    providers_to_randomize_fingerprint_for = [
        "cloudwatch",
        "datadog",
    ]

    provider_classes = {
        provider: ProvidersFactory.get_provider_class(provider)
        for provider in providers
    }

    existing_installed_providers = get_installed_providers(keep_api_key, keep_api_url)
    logger.info(f"Existing installed providers: {existing_installed_providers}")
    existing_providers_to_their_ids = {}

    for existing_provider in existing_installed_providers:
        if existing_provider["type"] in providers:
            existing_providers_to_their_ids[existing_provider["type"]] = (
                existing_provider["id"]
            )
    logger.info(
        f"Existing installed existing_providers_to_their_ids: {existing_providers_to_their_ids}"
    )

    if demo_correlation_rules:
        logger.info("Creating correlation rules...")
        get_or_create_correlation_rules(keep_api_key, keep_api_url)
        logger.info("Correlation rules created.")

    if demo_topology:
        logger.info("Creating topology...")
        get_or_create_topology(keep_api_key, keep_api_url)
        logger.info("Topology created.")

    while True:
        try:
            logger.info("Looping to send alerts...")

            if clean_old_incidents:
                logger.info("Removing old incidents...")
                remove_old_incidents(keep_api_key, keep_api_url)
                logger.info("Old incidents removed.")

            send_alert_url_params = {}

            # choose provider
            provider_type = random.choice(providers)
            send_alert_url = "{}/alerts/event/{}".format(keep_api_url, provider_type)

            if provider_type in existing_providers_to_their_ids:
                send_alert_url_params["provider_id"] = existing_providers_to_their_ids[
                    provider_type
                ]
            logger.info(
                f"Provider type: {provider_type}, send_alert_url_params now are: {send_alert_url_params}"
            )

            provider = provider_classes[provider_type]
            alert = provider.simulate_alert()

            if provider_type in providers_to_randomize_fingerprint_for:
                send_alert_url_params["fingerprint"] = str(uuid4())

            # Determine number of times to send the same alert
            num_iterations = 1
            if GENERATE_DEDUPLICATIONS:
                num_iterations = random.randint(1, 3)

            for _ in range(num_iterations):
                logger.info("Sending alert: {}".format(alert))
                try:
                    env = random.choice(["production", "staging", "development"])

                    if "provider_id" not in send_alert_url_params:
                        send_alert_url_params["provider_id"] = f"{provider_type}-{env}"
                    else:
                        alert["environment"] = random.choice(
                            ["prod-01", "prod-02", "prod-03"]
                        )

                    prepared_request = PreparedRequest()
                    prepared_request.prepare_url(send_alert_url, send_alert_url_params)
                    logger.info(
                        f"Sending alert to {prepared_request.url} with url params {send_alert_url_params}"
                    )

                    response = requests.post(
                        prepared_request.url,
                        headers={"x-api-key": keep_api_key},
                        json=alert,
                    )
                    response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    logger.error("Failed to send alert: {}".format(e))
                    time.sleep(sleep_interval)
                    continue

                if not response.ok:
                    logger.error("Failed to send alert: {}".format(response.text))
                else:
                    logger.info("Alert sent successfully")
        except Exception as e:
            logger.exception(
                "Error in simulate_alerts", extra={"exception_str": str(e)}
            )

        logger.info(
            "Sleeping for {} seconds before next iteration".format(sleep_interval)
        )
        time.sleep(sleep_interval)


def launch_demo_mode_thread(
    keep_api_url=None, keep_api_key=None
) -> threading.Thread | None:
    if not KEEP_LIVE_DEMO_MODE:
        logger.info("Not launching the demo mode.")
        return

    logger.info("Launching demo mode.")

    if keep_api_key is None:
        with get_session_sync() as session:
            keep_api_key = get_or_create_api_key(
                session=session,
                tenant_id=SINGLE_TENANT_UUID,
                created_by="system",
                unique_api_key_id="simulate_alerts",
                system_description="Simulate Alerts API key",
            )

    sleep_interval = 5

    thread = threading.Thread(
        target=simulate_alerts,
        kwargs={
            "keep_api_key": keep_api_key,
            "keep_api_url": keep_api_url,
            "sleep_interval": sleep_interval,
            "demo_correlation_rules": True,
            "demo_topology": True,
            "clean_old_incidents": True,
        },
    )
    thread.daemon = True
    thread.start()

    logger.info("Demo mode launched.")
    return thread
