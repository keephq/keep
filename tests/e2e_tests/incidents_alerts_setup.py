import time
from datetime import datetime, timedelta

import pytest
import requests
from playwright.sync_api import expect, Page


GRAFANA_HOST = "http://grafana:3000"
GRAFANA_HOST_LOCAL = "http://localhost:3002"
KEEP_UI_URL = "http://localhost:3000"
KEEP_API_URL = "http://localhost:8080"


def query_alerts(cell_query: str = None, limit: int = None, offset: int = None):
    url = f"{KEEP_API_URL}/alerts/query"

    query = {}

    if cell_query:
        query["cel"] = cell_query

    if limit is not None:
        query["limit"] = limit

    if offset is not None:
        query["offset"] = offset

    result: dict = None

    for _ in range(5):
        try:
            response = requests.post(
                url,
                json=query,
                headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
                timeout=5,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to query alerts: {e}")
            time.sleep(1)
            continue

    if result is None:
        raise Exception(f"Failed to query alerts after {5} attempts")

    grouped_alerts_by_name = {}

    for alert in result["results"]:
        grouped_alerts_by_name.setdefault(alert["name"], []).append(alert)

    return {
        "results": result["results"],
        "count": result["count"],
        "grouped_by_name": grouped_alerts_by_name,
    }


def create_fake_alert(index: int, provider_type: str):
    title = "Low Disk Space"
    status = "firing"
    severity = "critical"
    custom_tag = "environment:production"
    test_alert_id = f"alert-finger-print-{index}"

    if index % 4 == 0:
        title = "High CPU Usage"
        status = "resolved"
        severity = "warning"
        custom_tag = "environment:development"
    elif index % 3 == 0:
        title = "Memory Usage High"
        severity = "info"
        custom_tag = "environment:staging"
    elif index % 2 == 0:
        title = "Network Error"
        status = "suppressed"
        severity = "high"
        custom_tag = "environment:custom"

    if index % 5 == 0:
        title += "Enriched"

    if provider_type == "datadog":
        SEVERITIES_MAP = {
            "info": "P4",
            "warning": "P3",
            "high": "P2",
            "critical": "P1",
        }

        STATUS_MAP = {
            "firing": "Triggered",
            "resolved": "Recovered",
            "suppressed": "Muted",
        }
        alert_name = f"[{SEVERITIES_MAP.get(severity, SEVERITIES_MAP['critical'])}] [{STATUS_MAP.get(status, STATUS_MAP['firing'])}] {title} {provider_type} {index}"

        return {
            "alertName": alert_name,
            "title": alert_name,
            "type": "metric alert",
            "query": "avg(last_5m):avg:system.cpu.user{*} by {host} > 90",
            # Leading index is for easier result verification in sort tests
            "message": f"{index} CPU usage is over 90% on srv1-eu1-prod. Searched value: {'even' if index % 2 else 'odd'}",
            "description": "CPU usage is over 90% on srv1-us2-prod.",
            "tagsList": "environment:production,team:backend,monitor,service:api",
            "priority": "P2",
            "monitor_id": test_alert_id,
            "scopes": "srv2-eu1-prod",
            "host.name": "srv2-ap1-prod",
            "last_updated": 1739114561286,
            "alert_transition": STATUS_MAP.get(status, "Triggered"),
            "date_happened": (datetime.utcnow() + timedelta(days=-index)).timestamp(),
            "tags": {
                "envNameTag": "production" if index % 2 else "development",
                "testAlertId": test_alert_id,
            },
            "custom_tags": {
                "env": custom_tag,
            },
            "id": test_alert_id,
        }
    elif provider_type == "prometheus":
        SEVERITIES_MAP = {
            "critical": "critical",
            "high": "error",
            "warning": "warning",
            "info": "info",
            "low": "low",
        }
        STATUS_MAP = {
            "firing": "firing",
            "resolved": "firing",
        }
        alert_name = f"{title} {provider_type} {index} summary"

        return {
            "alertName": alert_name,
            "testAlertId": test_alert_id,
            "summary": alert_name,
            "labels": {
                "severity": SEVERITIES_MAP.get(severity, SEVERITIES_MAP["critical"]),
                "host": "host1",
                "service": "calendar-producer-java-otel-api-dd",
                "instance": "instance2",
                "alertname": alert_name,
            },
            "status": STATUS_MAP.get(status, STATUS_MAP["firing"]),
            "annotations": {
                # Leading index is for easier result verification in sort tests
                "summary": f"{index} {title} {provider_type}. It's not normal for customer_id:acme",
            },
            "startsAt": "2025-02-09T17:26:12.769318+00:00",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://example.com/graph?g0.expr=NetworkLatencyHigh",
            "fingerprint": test_alert_id,
            "custom_tags": {
                "env": custom_tag,
            },
        }


def upload_alerts():
    current_alerts = query_alerts(limit=1000, offset=0)
    simulated_alerts = []

    for alert_index, provider_type in enumerate(["datadog"] * 10 + ["prometheus"] * 10):
        alert = create_fake_alert(alert_index, provider_type)
        alert["dateForTests"] = (
            datetime(2025, 2, 10, 10) + timedelta(days=-alert_index)
        ).isoformat()

        simulated_alerts.append((provider_type, alert))

    not_uploaded_alerts = []

    for provider_type, alert in simulated_alerts:
        if alert["alertName"] not in current_alerts["grouped_by_name"]:
            not_uploaded_alerts.append((provider_type, alert))

    for provider_type, alert in not_uploaded_alerts:
        url = f"{KEEP_API_URL}/alerts/event/{provider_type}"
        requests.post(
            url,
            json=alert,
            timeout=5,
            headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
        ).raise_for_status()
        time.sleep(
            1
        )  # this is important for sorting by lastReceived. We need to have different lastReceived for alerts

    if not not_uploaded_alerts:
        return current_alerts

    attempt = 0
    while True:
        time.sleep(1)
        current_alerts = query_alerts(limit=1000, offset=0)
        attempt += 1

        if all(
            simluated_alert["alertName"] in current_alerts["grouped_by_name"]
            for _, simluated_alert in simulated_alerts
        ):
            break

        if attempt >= 10:
            raise Exception(
                f"Not all alerts were uploaded. Not uploaded alerts: {not_uploaded_alerts}"
            )

    alerts_to_enrich = [
        alert for alert in current_alerts["results"] if "Enriched" in alert["name"]
    ]

    for alert in alerts_to_enrich:
        url = f"{KEEP_API_URL}/alerts/enrich"
        requests.post(
            url,
            json={
                "enrichments": {"status": "enriched status"},
                "fingerprint": alert["fingerprint"],
            },
            timeout=5,
            headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
        ).raise_for_status()

    return query_alerts(limit=1000, offset=0)


def upload_alert(provider_type, alert):
    url = f"{KEEP_API_URL}/alerts/event/{provider_type}"
    requests.post(
        url,
        json=alert,
        timeout=5,
        headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
    ).raise_for_status()


def query_incidents(cell_query: str = None, limit: int = None, offset: int = None):
    url = f"{KEEP_API_URL}/incidents"

    query = {}

    if cell_query:
        query["cel"] = cell_query

    if limit is not None:
        query["limit"] = limit

    if offset is not None:
        query["offset"] = offset

    if query:
        url += "?"
        url += "&".join([f"{key}={value}" for key, value in query.items()])

    result: dict = None

    for _ in range(5):
        try:
            response = requests.get(
                url,
                json=query,
                headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
                timeout=5,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to query incidents: {e}")
            time.sleep(1)
            continue

    if result is None:
        raise Exception(f"Failed to query incidents after {5} attempts")

    grouped_alerts_by_name = {}

    for incident in result["items"]:
        grouped_alerts_by_name.setdefault(incident["user_generated_name"], []).append(
            incident
        )

    return {
        "results": result["items"],
        "count": result["count"],
        "grouped_by_name": grouped_alerts_by_name,
    }


# def get_incident_alerts(incident_id: str):
#     url = f"{KEEP_API_URL}/incidents/{incident_id}/alerts"

#     result: dict = None

#     for _ in range(5):
#         try:
#             response = requests.get(
#                 url,
#                 headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
#                 timeout=5,
#             )
#             response.raise_for_status()
#             result = response.json()
#         except requests.exceptions.RequestException as e:
#             print(f"Failed to query alert for incident {incident_id}: {e}")
#             time.sleep(1)
#             continue

#     if result is None:
#         raise Exception(
#             f"Failed to query alerts for incident {incident_id} after {5} attempts"
#         )

#     grouped_alerts_by_name = {}

#     for incident in result["items"]:
#         grouped_alerts_by_name.setdefault(incident["user_generated_name"], []).append(
#             incident
#         )

#     return {
#         "results": result["items"],
#         "count": result["count"],
#         "grouped_by_name": grouped_alerts_by_name,
#     }


def create_fake_incident(index: int):
    return {
        "assignee": "",
        "resolve_on": "all",
        "user_generated_name": f"Incident name {index}",
        "user_summary": f"Incident summary {index}",
    }


def upload_incidents():
    current_incidents = query_incidents(limit=1000, offset=0)
    simulated_incidents = []

    for incident_index in range(20):
        incident = create_fake_incident(incident_index)
        simulated_incidents.append(incident)

    not_uploaded_incidents = []

    for incident in simulated_incidents:
        if incident["user_generated_name"] not in current_incidents["grouped_by_name"]:
            not_uploaded_incidents.append(incident)

    for incident in not_uploaded_incidents:
        url = f"{KEEP_API_URL}/incidents"
        requests.post(
            url,
            json=incident,
            timeout=5,
            headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
        ).raise_for_status()
        time.sleep(1)

    if not not_uploaded_incidents:
        return current_incidents

    attempt = 0
    while True:
        time.sleep(1)
        current_incidents = query_incidents(limit=1000, offset=0)
        attempt += 1

        if all(
            simluated_incident["user_generated_name"]
            in current_incidents["grouped_by_name"]
            for simluated_incident in simulated_incidents
        ):
            break

        if attempt >= 10:
            raise Exception(
                f"Not all incidents were uploaded. Not uploaded incidents: {not_uploaded_incidents}"
            )

    # for index, item in enumerate(current_incidents["results"]):
    #     if

    return query_incidents(limit=1000, offset=0)


def associate_alerts_with_incident(incident_id: str, alert_ids: list[str]):
    url = f"{KEEP_API_URL}/incidents/{incident_id}/alerts"
    requests.post(
        url,
        json=alert_ids,
        timeout=5,
        headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
    ).raise_for_status()


def setup_incidents_alerts():
    alerts_query_result = upload_alerts()
    incidents_query_result = upload_incidents()

    for index, incident in enumerate(incidents_query_result["results"]):
        incident_id = incident["id"]
        incident_alerts = alerts_query_result["results"][index * 2 : index * 2 + 2]
        associate_alerts_with_incident(
            incident_id, [alert["id"] for alert in incident_alerts]
        )

    return {
        "alerts": alerts_query_result["results"],
        "incidents": incidents_query_result["results"],
    }
