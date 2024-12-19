import asyncio
import datetime
import logging
import os
import random
import threading
import time
from datetime import timezone
from uuid import uuid4

import aiohttp
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
GENERATE_DEDUPLICATIONS = False

REQUESTS_QUEUE = asyncio.Queue()

correlation_rules_to_create = [
    {
        "sqlQuery": {"sql": "((name like :name_1))", "params": {"name_1": "%MQ%"}},
        "groupDescription": "This rule groups all alerts related to MQ.",
        "ruleName": "Message queue is getting filled up",
        "celQuery": '(name.contains("MQ"))',
        "timeframeInSeconds": 86400,
        "timeUnit": "hours",
        "groupingCriteria": [],
        "requireApprove": False,
        "resolveOn": "never",
    },
    {
        "sqlQuery": {
            "sql": "((name like :name_1) or (name = :name_2) or (name like :name_3)) or (name = :name_4)",
            "params": {
                "name_1": "%NetworkLatencyHigh%",
                "name_2": "HighCPUUsage",
                "name_3": "%NetworkLatencyIsHigh%",
                "name_4": "Failed to load product catalog",
            },
        },
        "groupDescription": "This rule groups alerts from multiple sources.",
        "ruleName": "Application issue caused by DB load",
        "celQuery": '(name.contains("NetworkLatencyHigh")) || (name == "HighCPUUsage") || (name.contains("NetworkLatencyIsHigh")) || (name == "Failed to load product catalog")',
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


def perform_demo_ai(keep_api_key, keep_api_url):
    # Get or create manual Incident
    incidents_existing = requests.get(
        f"{keep_api_url}/incidents",
        headers={"x-api-key": keep_api_key},
    )
    incidents_existing.raise_for_status()
    incidents_existing = incidents_existing.json()["items"]

    MANUAL_INCIDENT_NAME = "GPU Cluster issue"

    incident_exists = None

    # Create incident if it doesn't exist

    for incident in incidents_existing:
        if incident["user_generated_name"] == MANUAL_INCIDENT_NAME:
            incident_exists = incident

    if incident_exists is None:
        response = requests.post(
            f"{keep_api_url}/incidents",
            headers={"x-api-key": keep_api_key},
            json={
                "user_generated_name": MANUAL_INCIDENT_NAME,
                "user_summary": "While two other incidents are created because of correlation rules, this incident is created manually and only a few alerts are added to it. AI will correlated it with the rest of alerts automatically.",
                "severity": "critical",
                "status": "open",
                "environment": "prod",
                "service": "api",
                "application": "Main App",
                "description": "This is a manual incident.",
            },
        )
        response.raise_for_status()

    random_number = random.randint(1, 100)
    if random_number > 90:
        return

    # Publish alert

    FAKE_ALERT_NAMES = [
        "HighGPUConsumption",
        "NotMuchGPUMemoryLeft",
        "GPUServiceError",
    ]
    name = random.choice(FAKE_ALERT_NAMES)

    DESCRIPTIONS = {
        "HighGPUConsumption": "GPU usage is high",
        "NotMuchGPUMemoryLeft": "GPU memory latency is high",
        "GPUServiceError": "GPU service is probably unreachable",
    }

    response = requests.post(
        f"{keep_api_url}/alerts/event",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": keep_api_key,
        },
        json={
            "name": name,
            "source": ["prometheus"],
            "description": DESCRIPTIONS[name],
            "fingerprint": str(uuid4()),
        },
    )
    response.raise_for_status()

    # If incident has not many alerts, correlate

    alerts_in_incident = requests.get(
        f"{keep_api_url}/incidents/{incident_exists['id']}/alerts",
        headers={"x-api-key": keep_api_key},
    )
    alerts_in_incident.raise_for_status()
    alerts_in_incident = alerts_in_incident.json()

    if len(alerts_in_incident["items"]) < 20:
        alerts_existing = requests.get(
            f"{keep_api_url}/alerts",
            headers={"x-api-key": keep_api_key},
        )
        alerts_existing.raise_for_status()
        alerts_existing = alerts_existing.json()
        fingerprints_to_add = []
        for alert in alerts_existing:
            if alert["name"] in FAKE_ALERT_NAMES:
                fingerprints_to_add.append(alert["fingerprint"])

        if len(fingerprints_to_add) > 0:
            fingerprints_to_add = fingerprints_to_add[:10]

            response = requests.post(
                f"{keep_api_url}/incidents/{incident_exists['id']}/alerts",
                headers={"x-api-key": keep_api_key},
                json=fingerprints_to_add,
            )
            response.raise_for_status()


def simulate_alerts(*args, **kwargs):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(simulate_alerts_worker(0, kwargs.get("keep_api_key"), 0))
    loop.create_task(simulate_alerts_async(*args, **kwargs))
    loop.run_forever()


async def simulate_alerts_async(
    keep_api_url=None,
    keep_api_key=None,
    sleep_interval=5,
    demo_correlation_rules=False,
    demo_topology=False,
    clean_old_incidents=False,
    demo_ai=False,
    target_rps=0,
):
    logger.info("Simulating alerts...")

    providers_config = [
        {"type": "prometheus", "weight": 3},
        {"type": "grafana", "weight": 1},
        {"type": "cloudwatch", "weight": 1},
        {"type": "datadog", "weight": 1},
        {"type": "sentry", "weight": 2},
        # {"type": "signalfx", "weight": 1},
        {"type": "gcpmonitoring", "weight": 1},
    ]

    # Normalize weights
    total_weight = sum(p["weight"] for p in providers_config)
    normalized_weights = [p["weight"] / total_weight for p in providers_config]

    providers = [p["type"] for p in providers_config]

    providers_to_randomize_fingerprint_for = [
        # "cloudwatch",
        # "datadog",
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

    shoot = 1
    while True:
        try:
            logger.info("Looping to send alerts...")

            if clean_old_incidents:
                logger.info("Removing old incidents...")
                remove_old_incidents(keep_api_key, keep_api_url)
                logger.info("Old incidents removed.")

            if demo_ai:
                perform_demo_ai(keep_api_key, keep_api_url)

            # If we want to make stress-testing, we want to prepare more data for faster requesting in workers
            if target_rps:
                shoot = target_rps * 100

            for _ in range(shoot):

                send_alert_url_params = {}

                # choose provider based on weights
                provider_type = random.choices(
                    providers, weights=normalized_weights, k=1
                )[0]
                send_alert_url = "{}/alerts/event/{}".format(
                    keep_api_url, provider_type
                )

                if provider_type in existing_providers_to_their_ids:
                    send_alert_url_params["provider_id"] = (
                        existing_providers_to_their_ids[provider_type]
                    )
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

                env = random.choice(["production", "staging", "development"])

                if "provider_id" not in send_alert_url_params:
                    send_alert_url_params["provider_id"] = f"{provider_type}-{env}"
                else:
                    alert["environment"] = random.choice(
                        ["prod-01", "prod-02", "prod-03"]
                    )

                for _ in range(num_iterations):

                    prepared_request = PreparedRequest()
                    prepared_request.prepare_url(send_alert_url, send_alert_url_params)
                    await REQUESTS_QUEUE.put((prepared_request.url, alert))
                    if not target_rps:
                        await asyncio.sleep(sleep_interval)

            # Wait until almost prepopulated data was consumed
            while not REQUESTS_QUEUE.empty():
                await asyncio.sleep(sleep_interval)

        except Exception as e:
            logger.exception(
                "Error in simulate_alerts", extra={"exception_str": str(e)}
            )

        logger.info(
            "Sleeping for {} seconds before next iteration".format(sleep_interval)
        )
        await asyncio.sleep(sleep_interval)


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
            "demo_ai": True,
        },
    )
    thread.daemon = True
    thread.start()

    logger.info("Demo mode launched.")
    return thread


async def simulate_alerts_worker(worker_id, keep_api_key, rps=1):

    headers = {"x-api-key": keep_api_key, "Content-type": "application/json"}

    async with aiohttp.ClientSession() as session:
        total_start = time.time()
        total_requests = 0
        while True:
            start = time.time()
            url, alert = await REQUESTS_QUEUE.get()

            async with session.post(url, json=alert, headers=headers) as response:
                total_requests += 1
                if not response.ok:
                    logger.error("Failed to send alert: {}".format(response.text))
                else:
                    logger.info("Alert sent successfully")

            if rps:
                delay = 1 / rps - (time.time() - start)
                if delay > 0:
                    logger.debug("worker %d sleeps, %f", worker_id, delay)
                    await asyncio.sleep(delay)
            logger.info(
                "Worker %d RPS: %.2f",
                worker_id,
                total_requests / (time.time() - total_start),
            )


if __name__ == "__main__":
    keep_api_url = os.environ.get("KEEP_API_URL") or "http://localhost:8080"
    keep_api_key = os.environ.get("KEEP_READ_ONLY_BYPASS_KEY")
    get_or_create_correlation_rules(keep_api_key, keep_api_url)
    simulate_alerts(
        keep_api_url=keep_api_url,
        keep_api_key=keep_api_key,
        sleep_interval=1,
        demo_correlation_rules=True,
    )
