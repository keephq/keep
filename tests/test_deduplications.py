import random
import time
import uuid

import pytest

from keep.providers.providers_factory import ProvidersFactory
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


def wait_for_alerts(client, num_alerts):
    alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()
    print(f"------------- Total alerts: {len(alerts)}")
    while len(alerts) != num_alerts:
        time.sleep(1)
        alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()
        print(f"------------- Total alerts: {len(alerts)}")


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_default_deduplication_rule(db_session, client, test_app):
    # insert an alert with some provider_id and make sure that the default deduplication rule is working
    provider_classes = {
        provider: ProvidersFactory.get_provider_class(provider)
        for provider in ["datadog", "prometheus"]
    }
    for provider_type, provider in provider_classes.items():
        alert = provider.simulate_alert()
        client.post(
            f"/alerts/event/{provider_type}?",
            json=alert,
            headers={"x-api-key": "some-api-key"},
        )

    wait_for_alerts(client, 2)

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()
    assert len(deduplication_rules) == 3  # default + datadog + prometheus

    for dedup_rule in deduplication_rules:
        # check that the default deduplication rule is working
        if dedup_rule.get("provider_type") == "keep":
            assert dedup_rule.get("ingested") == 0
            assert dedup_rule.get("default")
            # check how many times the alert was deduplicated in the last 24 hours
            assert dedup_rule.get("distribution") == [
                {"hour": i, "number": 0} for i in range(24)
            ]
        # check that the datadog/prometheus deduplication rule is working
        else:
            assert dedup_rule.get("ingested") == 1
            # the deduplication ratio is zero since the alert was not deduplicated
            assert dedup_rule.get("dedup_ratio") == 0
            assert dedup_rule.get("default")


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_deduplication_sanity(db_session, client, test_app):
    # insert the same alert twice and make sure that the default deduplication rule is working
    # insert an alert with some provider_id and make sure that the default deduplication rule is working
    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()
    for i in range(2):
        client.post(
            "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
        )

    wait_for_alerts(client, 1)

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()
    while not any([rule for rule in deduplication_rules if rule.get("ingested") == 2]):
        time.sleep(1)
        deduplication_rules = client.get(
            "/deduplications", headers={"x-api-key": "some-api-key"}
        ).json()

    assert len(deduplication_rules) == 2  # default + datadog

    for dedup_rule in deduplication_rules:
        # check that the default deduplication rule is working
        if dedup_rule.get("provider_type") == "keep":
            assert dedup_rule.get("ingested") == 0
            assert dedup_rule.get("default")
        # check that the datadog/prometheus deduplication rule is working
        else:
            assert dedup_rule.get("ingested") == 2
            # the deduplication ratio is zero since the alert was not deduplicated
            assert dedup_rule.get("dedup_ratio") == 50.0
            assert dedup_rule.get("default")


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_deduplication_sanity_2(db_session, client, test_app):
    # insert two different alerts, twice each, and make sure that the default deduplication rule is working
    provider = ProvidersFactory.get_provider_class("datadog")
    alert1 = provider.simulate_alert()
    alert2 = alert1
    # datadog deduplicated by monitor_id
    while alert2.get("monitor_id") == alert1.get("monitor_id"):
        alert2 = provider.simulate_alert()

    for alert in [alert1, alert2]:
        for _ in range(2):
            client.post(
                "/alerts/event/datadog",
                json=alert,
                headers={"x-api-key": "some-api-key"},
            )

    wait_for_alerts(client, 2)

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    assert len(deduplication_rules) == 2  # default + datadog

    for dedup_rule in deduplication_rules:
        if dedup_rule.get("provider_type") == "datadog":
            assert dedup_rule.get("ingested") == 4
            assert dedup_rule.get("dedup_ratio") == 50.0
            assert dedup_rule.get("default")


@pytest.mark.timeout(20)
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_deduplication_sanity_3(db_session, client, test_app):
    # insert many alerts and make sure that the default deduplication rule is working
    provider = ProvidersFactory.get_provider_class("datadog")
    alerts = [provider.simulate_alert() for _ in range(10)]

    monitor_ids = set()
    for alert in alerts:
        # lets make it not deduplicated by randomizing the monitor_id
        while alert["monitor_id"] in monitor_ids:
            alert["monitor_id"] = random.randint(0, 10**10)
        monitor_ids.add(alert["monitor_id"])
        client.post(
            "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
        )

    wait_for_alerts(client, 10)

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    assert len(deduplication_rules) == 2  # default + datadog

    for dedup_rule in deduplication_rules:
        if dedup_rule.get("provider_type") == "datadog":
            assert dedup_rule.get("ingested") == 10
            assert dedup_rule.get("dedup_ratio") == 0
            assert dedup_rule.get("default")


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_custom_deduplication_rule(db_session, client, test_app):
    provider = ProvidersFactory.get_provider_class("datadog")
    alert1 = provider.simulate_alert()
    client.post(
        "/alerts/event/datadog", json=alert1, headers={"x-api-key": "some-api-key"}
    )

    # wait for the background tasks to finish
    wait_for_alerts(client, 1)

    # create a custom deduplication rule and insert alerts that should be deduplicated by this
    custom_rule = {
        "name": "Custom Rule",
        "description": "Custom Rule Description",
        "provider_type": "datadog",
        "fingerprint_fields": ["title", "message"],
        "full_deduplication": False,
        "ignore_fields": None,
    }

    resp = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
    assert resp.status_code == 200

    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()

    for _ in range(2):
        client.post(
            "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
        )

    wait_for_alerts(client, 2)

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    while not any([rule for rule in deduplication_rules if rule.get("ingested") == 2]):
        time.sleep(1)
        deduplication_rules = client.get(
            "/deduplications", headers={"x-api-key": "some-api-key"}
        ).json()

    custom_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("name") == "Custom Rule":
            custom_rule_found = True
            assert dedup_rule.get("ingested") == 2
            assert dedup_rule.get("dedup_ratio") == 50.0
            assert not dedup_rule.get("default")

    assert custom_rule_found


@pytest.mark.timeout(20)
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_custom_deduplication_rule_behaviour(db_session, client, test_app):
    # create a custom deduplication rule and insert alerts that should be deduplicated by this
    provider = ProvidersFactory.get_provider_class("datadog")
    alert1 = provider.simulate_alert()
    client.post(
        "/alerts/event/datadog", json=alert1, headers={"x-api-key": "some-api-key"}
    )

    # wait for the background tasks to finish
    wait_for_alerts(client, 1)

    custom_rule = {
        "name": "Custom Rule",
        "description": "Custom Rule Description",
        "provider_type": "datadog",
        "fingerprint_fields": ["title", "message"],
        "full_deduplication": False,
        "ignore_fields": None,
    }

    resp = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
    assert resp.status_code == 200

    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()

    for _ in range(2):
        # the default rule should deduplicate the alert by monitor_id so let's randomize it -
        # if the custom rule is working, the alert should be deduplicated by title and message
        alert["monitor_id"] = random.randint(0, 10**10)
        client.post(
            "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
        )

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    while not any(
        [rule for rule in deduplication_rules if rule.get("dedup_ratio") == 50.0]
    ):
        time.sleep(1)
        deduplication_rules = client.get(
            "/deduplications", headers={"x-api-key": "some-api-key"}
        ).json()

    custom_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("name") == "Custom Rule":
            custom_rule_found = True
            assert dedup_rule.get("ingested") == 2
            assert dedup_rule.get("dedup_ratio") == 50.0
            assert not dedup_rule.get("default")

    assert custom_rule_found


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"keepDatadog":{"type":"datadog","authentication":{"api_key":"1234","app_key": "1234"}}}',
        },
    ],
    indirect=True,
)
def test_custom_deduplication_rule_2(db_session, client, test_app):
    # create a custom full deduplication rule and insert alerts that should not be deduplicated by this
    providers = client.get("/providers", headers={"x-api-key": "some-api-key"}).json()
    datadog_provider_id = next(
        provider["id"]
        for provider in providers.get("installed_providers")
        if provider["type"] == "datadog"
    )

    custom_rule = {
        "name": "Custom Rule",
        "description": "Custom Rule Description",
        "provider_type": "datadog",
        "provider_id": datadog_provider_id,
        "fingerprint_fields": [
            "name",
            "message",
        ],  # title in datadog mapped to name in keep
        "full_deduplication": False,
        "ignore_fields": ["field_that_never_exists"],
    }

    response = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 200

    provider = ProvidersFactory.get_provider_class("datadog")
    alert1 = provider.simulate_alert()

    client.post(
        f"/alerts/event/datadog?provider_id={datadog_provider_id}",
        json=alert1,
        headers={"x-api-key": "some-api-key"},
    )
    alert1["title"] = "Different title"
    client.post(
        f"/alerts/event/datadog?provider_id={datadog_provider_id}",
        json=alert1,
        headers={"x-api-key": "some-api-key"},
    )

    # wait for the background tasks to finish
    alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()
    while len(alerts) < 2:
        time.sleep(1)
        alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    custom_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("name") == "Custom Rule":
            custom_rule_found = True
            assert dedup_rule.get("ingested") == 2
            assert dedup_rule.get("dedup_ratio") == 0
            assert not dedup_rule.get("default")

    assert custom_rule_found


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"keepDatadog":{"type":"datadog","authentication":{"api_key":"1234","app_key": "1234"}}}',
        },
    ],
    indirect=True,
)
def test_update_deduplication_rule(db_session, client, test_app):
    # create a custom deduplication rule and update it
    response = client.get("/providers", headers={"x-api-key": "some-api-key"})
    assert response.status_code == 200
    datadog_provider_id = next(
        provider["id"]
        for provider in response.json().get("installed_providers")
        if provider["type"] == "datadog"
    )

    custom_rule = {
        "name": "Custom Rule",
        "description": "Custom Rule Description",
        "provider_type": "datadog",
        "provider_id": datadog_provider_id,
        "fingerprint_fields": ["title", "message"],
        "full_deduplication": False,
        "ignore_fields": None,
    }

    response = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 200

    rule_id = response.json().get("id")
    updated_rule = {
        "name": "Updated Custom Rule",
        "description": "Updated Custom Rule",
        "provider_type": "datadog",
        "provider_id": datadog_provider_id,
        "fingerprint_fields": ["title"],
        "full_deduplication": False,
        "ignore_fields": None,
    }

    response = client.put(
        f"/deduplications/{rule_id}",
        json=updated_rule,
        headers={"x-api-key": "some-api-key"},
    )
    assert response.status_code == 200

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    updated_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("id") == rule_id:
            updated_rule_found = True
            assert dedup_rule.get("description") == "Updated Custom Rule"
            assert dedup_rule.get("fingerprint_fields") == ["title"]

    assert updated_rule_found


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_update_deduplication_rule_non_exist_provider(db_session, client, test_app):
    # create a custom deduplication rule and update it
    custom_rule = {
        "name": "Custom Rule",
        "description": "Custom Rule Description",
        "provider_type": "datadog",
        "fingerprint_fields": ["title", "message"],
        "full_deduplication": False,
        "ignore_fields": None,
    }
    response = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Provider datadog not found"}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_update_deduplication_rule_linked_provider(db_session, client, test_app):
    provider = ProvidersFactory.get_provider_class("datadog")
    alert1 = provider.simulate_alert()
    response = client.post(
        "/alerts/event/datadog", json=alert1, headers={"x-api-key": "some-api-key"}
    )

    time.sleep(2)
    custom_rule = {
        "name": "Custom Rule",
        "description": "Custom Rule Description",
        "provider_type": "datadog",
        "fingerprint_fields": ["title", "message"],
        "full_deduplication": False,
        "ignore_fields": None,
    }
    response = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
    # once a linked provider is created, a customization should be allowed
    assert response.status_code == 200


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"keepDatadog":{"type":"datadog","authentication":{"api_key":"1234","app_key": "1234"}}}',
        },
    ],
    indirect=True,
)
def test_delete_deduplication_rule_sanity(db_session, client, test_app):
    response = client.get("/providers", headers={"x-api-key": "some-api-key"})
    assert response.status_code == 200
    datadog_provider_id = next(
        provider["id"]
        for provider in response.json().get("installed_providers")
        if provider["type"] == "datadog"
    )
    # create a custom deduplication rule and delete it
    custom_rule = {
        "name": "Custom Rule",
        "description": "Custom Rule Description",
        "provider_type": "datadog",
        "provider_id": datadog_provider_id,
        "fingerprint_fields": ["title", "message"],
        "full_deduplication": False,
        "ignore_fields": None,
    }

    response = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 200

    rule_id = response.json().get("id")
    client.delete(f"/deduplications/{rule_id}", headers={"x-api-key": "some-api-key"})

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    assert all(rule.get("id") != rule_id for rule in deduplication_rules)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_delete_deduplication_rule_invalid(db_session, client, test_app):
    # try to delete a deduplication rule that does not exist
    response = client.delete(
        "/deduplications/non-existent-id", headers={"x-api-key": "some-api-key"}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid rule id"}

    # now use UUID
    some_uuid = str(uuid.uuid4())
    response = client.delete(
        f"/deduplications/{some_uuid}", headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_delete_deduplication_rule_default(db_session, client, test_app):
    # shoot an alert to create a default deduplication rule
    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()
    client.post(
        "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
    )

    alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()
    while len(alerts) != 1:
        time.sleep(1)
        alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()

    # try to delete a default deduplication rule
    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    default_rule_id = next(
        rule["id"] for rule in deduplication_rules if rule["default"]
    )

    response = client.delete(
        f"/deduplications/{default_rule_id}", headers={"x-api-key": "some-api-key"}
    )

    assert response.status_code == 404


"""
SHAHAR: should be resolved

@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_full_deduplication(db_session, client, test_app):
    # create a custom deduplication rule with full deduplication and insert alerts that should be deduplicated by this
    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()
    # send the alert so a linked provider is created
    response = client.post(
        "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
    )
    custom_rule = {
        "name": "Full Deduplication Rule",
        "description": "Full Deduplication Rule",
        "provider_type": "datadog",
        "fingerprint_fields": ["title", "message", "source"],
        "full_deduplication": True,
        "ignore_fields": list(alert.keys()),  # ignore all fields
    }

    response = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
    assert response.status_code == 200

    for _ in range(3):
        client.post(
            "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
        )

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    full_dedup_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("description") == "Full Deduplication Rule":
            full_dedup_rule_found = True
            assert dedup_rule.get("ingested") == 3
            assert 66.667 - dedup_rule.get("dedup_ratio") < 0.1  # 0.66666666....7

    assert full_dedup_rule_found
"""


@pytest.mark.timeout(15)
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_partial_deduplication(db_session, client, test_app):
    # insert a datadog alert with the same incident_id, group and title and make sure that the datadog default deduplication rule is working
    provider = ProvidersFactory.get_provider_class("datadog")
    base_alert = provider.simulate_alert()

    alerts = [
        base_alert,
        {**base_alert, "message": "Different message"},
        {**base_alert, "source": "Different source"},
    ]

    for alert in alerts:
        client.post(
            "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
        )

    wait_for_alerts(client, 1)

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    while not any([rule for rule in deduplication_rules if rule.get("ingested") == 3]):
        time.sleep(1)
        deduplication_rules = client.get(
            "/deduplications", headers={"x-api-key": "some-api-key"}
        ).json()

    datadog_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("provider_type") == "datadog" and dedup_rule.get("default"):
            datadog_rule_found = True
            assert dedup_rule.get("ingested") == 3
            assert (
                dedup_rule.get("dedup_ratio") > 0
                and dedup_rule.get("dedup_ratio") < 100
            )

    assert datadog_rule_found


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_ingesting_alert_without_fingerprint_fields(db_session, client, test_app):
    # insert a datadog alert without the required fingerprint fields and make sure that it is not deduplicated
    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()
    alert.pop("incident_id", None)
    alert.pop("group", None)
    alert["title"] = str(random.randint(0, 10**10))

    client.post(
        "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
    )

    alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()
    while len(alerts) != 1:
        time.sleep(1)
        alerts = client.get("/alerts", headers={"x-api-key": "some-api-key"}).json()

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    datadog_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("provider_type") == "datadog" and dedup_rule.get("default"):
            datadog_rule_found = True
            assert dedup_rule.get("ingested") == 1
            assert dedup_rule.get("dedup_ratio") == 0

    assert datadog_rule_found


@pytest.mark.timeout(15)
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_deduplication_fields(db_session, client, test_app):
    # insert a datadog alert with the same incident_id and make sure that the datadog default deduplication rule is working
    provider = ProvidersFactory.get_provider_class("datadog")
    base_alert = provider.simulate_alert()

    alerts = [
        base_alert,
        {**base_alert, "group": "Different group"},
        {**base_alert, "title": "Different title"},
    ]

    for alert in alerts:
        client.post(
            "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
        )

    wait_for_alerts(client, 1)

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    while not any([rule for rule in deduplication_rules if rule.get("ingested") == 3]):
        print("Waiting for deduplication rules to be ingested")
        time.sleep(1)
        deduplication_rules = client.get(
            "/deduplications", headers={"x-api-key": "some-api-key"}
        ).json()

    datadog_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("provider_type") == "datadog" and dedup_rule.get("default"):
            datadog_rule_found = True
            assert dedup_rule.get("ingested") == 3
            # @tb: couldn't understand this:
            # assert 66.667 - dedup_rule.get("dedup_ratio") < 0.1  # 0.66666666....7
    assert datadog_rule_found
