import logging
import time

import pytest

from keep.providers.providers_factory import ProvidersFactory
from tests.fixtures.client import client, setup_api_key, test_app  # noqa

# Set the log level to DEBUG
logging.basicConfig(level=logging.DEBUG)


def get_alert_by_fingerprint(client, fingerprint):
    """Helper function to get an alert by fingerprint"""
    alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()
    for alert in alerts:
        if alert.get("fingerprint") == fingerprint:
            return alert
    return None


@pytest.mark.timeout(15)
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_CALCULATE_START_FIRING_TIME_ENABLED": "true",
        },
    ],
    indirect=True,
)
def test_firing_counter_increment_on_same_alert(db_session, client, test_app):
    """Test that firing counter increments when the same alert fires multiple times."""
    # Get a simulated datadog alert
    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()
    # we want another alert with the same monitor id but different attributes (so alert is correlated)
    alert2 = provider.simulate_alert()
    alert2["monitor_id"] = alert["monitor_id"]
    alert2["scopes"] = alert["scopes"]

    # Send the alert
    response = client.post(
        "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 202

    # Wait for processing
    time.sleep(1)

    # Get the alert to check its initial firing counter
    alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()
    assert len(alerts) == 1

    fingerprint = alerts[0]["fingerprint"]
    assert alerts[0]["firingCounter"] == 1

    # Send the same alert again
    response = client.post(
        "/alerts/event/datadog", json=alert2, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 202

    # Wait for processing
    time.sleep(1)

    # Get the updated alert
    updated_alert = get_alert_by_fingerprint(client, fingerprint)
    assert updated_alert is not None
    assert updated_alert["firingCounter"] == 2


@pytest.mark.timeout(15)
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_CALCULATE_START_FIRING_TIME_ENABLED": "true",
        },
    ],
    indirect=True,
)
def test_firing_counter_reset_on_acknowledge(db_session, client, test_app):
    """Test that firing counter resets to 0 when an alert is acknowledged."""
    # Get a simulated datadog alert
    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()
    alert2 = provider.simulate_alert()
    alert2["monitor_id"] = alert["monitor_id"]
    alert2["scopes"] = alert["scopes"]

    # Send the alert
    response = client.post(
        "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 202

    # Wait for processing
    time.sleep(1)

    # Get the alert to check its initial firing counter
    alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()
    assert len(alerts) == 1

    fingerprint = alerts[0]["fingerprint"]
    assert alerts[0]["firingCounter"] == 1

    # Acknowledge the alert
    payload = {
        "enrichments": {
            "status": "acknowledged",
            "dismissed": False,
            "dismissUntil": "",
        },
        "fingerprint": alerts[0]["fingerprint"],
    }
    response = client.post(
        "/alerts/enrich?dispose_on_new_alert=true",
        json=payload,
        headers={"x-api-key": "some-api-key"},
    )
    assert response.status_code == 200

    # Wait for processing
    time.sleep(1)

    # Get the updated alert
    updated_alert = get_alert_by_fingerprint(client, fingerprint)
    assert updated_alert is not None
    assert updated_alert["firingCounter"] == 0

    # Fire the same alert again after it was acknowledged
    response = client.post(
        "/alerts/event/datadog", json=alert2, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 202

    # Wait for processing
    time.sleep(1)

    # Get the updated alert
    updated_alert = get_alert_by_fingerprint(client, fingerprint)
    assert updated_alert is not None
    assert updated_alert["firingCounter"] == 1


@pytest.mark.timeout(15)
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_CALCULATE_START_FIRING_TIME_ENABLED": "true",
        },
    ],
    indirect=True,
)
def test_firing_counter_with_different_status(db_session, client, test_app):
    """Test firing counter behavior with different alert statuses."""
    # Get a simulated datadog alert
    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()
    alert2 = provider.simulate_alert()
    alert2["monitor_id"] = alert["monitor_id"]
    alert2["scopes"] = alert["scopes"]
    alert["alert_transition"] = "Triggered"
    alert2["alert_transition"] = "Recovered"
    # Send the alert (FIRING by default)
    response = client.post(
        "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 202

    # Wait for processing
    time.sleep(1)

    # Get the alert to check its initial firing counter
    alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()
    assert len(alerts) == 1

    fingerprint = alerts[0]["fingerprint"]
    assert alerts[0]["firingCounter"] == 1

    response = client.post(
        "/alerts/event/datadog", json=alert2, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 202

    # Wait for processing
    time.sleep(1)

    # Get the updated alert
    resolved_alert = get_alert_by_fingerprint(client, fingerprint)
    assert resolved_alert is not None

    # Check status and firing counter (should keep previous value when resolved)
    assert resolved_alert["status"] == "resolved"
    # The counter will likely have incremented here since it's just a new alert with a different status
    resolved_firing_counter = resolved_alert["firingCounter"]

    response = client.post(
        "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 202

    # Wait for processing
    time.sleep(1)

    # Get the updated alert
    refired_alert = get_alert_by_fingerprint(client, fingerprint)
    assert refired_alert is not None
    assert refired_alert["status"] == "firing"
    # Should have incremented from the resolved state
    assert refired_alert["firingCounter"] == resolved_firing_counter + 1
