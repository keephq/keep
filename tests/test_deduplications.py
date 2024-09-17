import pytest

from keep.providers.providers_factory import ProvidersFactory
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


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

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    assert len(deduplication_rules) == 2  # default + datadog

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
    alert2 = provider.simulate_alert()

    for alert in [alert1, alert2]:
        for _ in range(2):
            client.post(
                "/alerts/event/datadog",
                json=alert,
                headers={"x-api-key": "some-api-key"},
            )

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    assert len(deduplication_rules) == 2  # default + datadog

    for dedup_rule in deduplication_rules:
        if dedup_rule.get("provider_type") == "datadog":
            assert dedup_rule.get("ingested") == 4
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
def test_deduplication_sanity_3(db_session, client, test_app):
    # insert many alerts and make sure that the default deduplication rule is working
    provider = ProvidersFactory.get_provider_class("datadog")
    alerts = [provider.simulate_alert() for _ in range(10)]

    for alert in alerts:
        client.post(
            "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
        )

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
    # create a custom deduplication rule and insert alerts that should be deduplicated by this
    custom_rule = {
        "description": "Custom Rule",
        "provider_type": "datadog",
        "deduplication_fields": ["title", "message"],
        "default": False,
    }

    client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )

    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()

    for _ in range(2):
        client.post(
            "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
        )

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    custom_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("description") == "Custom Rule":
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
        },
    ],
    indirect=True,
)
def test_custom_deduplication_rule_2(db_session, client, test_app):
    # create a custom deduplication rule and insert alerts that should not be deduplicated by this
    custom_rule = {
        "description": "Custom Rule",
        "provider_type": "datadog",
        "deduplication_fields": ["title", "message"],
        "default": False,
    }

    client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )

    provider = ProvidersFactory.get_provider_class("datadog")
    alert1 = provider.simulate_alert()
    alert2 = provider.simulate_alert()

    client.post(
        "/alerts/event/datadog", json=alert1, headers={"x-api-key": "some-api-key"}
    )
    client.post(
        "/alerts/event/datadog", json=alert2, headers={"x-api-key": "some-api-key"}
    )

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    custom_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("description") == "Custom Rule":
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
        },
    ],
    indirect=True,
)
def test_update_deduplication_rule(db_session, client, test_app):
    # create a custom deduplication rule and update it
    custom_rule = {
        "description": "Custom Rule",
        "provider_type": "datadog",
        "deduplication_fields": ["title", "message"],
        "default": False,
    }

    response = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
    rule_id = response.json().get("id")

    updated_rule = {
        "description": "Updated Custom Rule",
        "provider_type": "datadog",
        "deduplication_fields": ["title"],
        "default": False,
    }

    client.put(
        f"/deduplications/{rule_id}",
        json=updated_rule,
        headers={"x-api-key": "some-api-key"},
    )

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    updated_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("id") == rule_id:
            updated_rule_found = True
            assert dedup_rule.get("description") == "Updated Custom Rule"
            assert dedup_rule.get("deduplication_fields") == ["title"]

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
def test_delete_deduplication_rule_sanity(db_session, client, test_app):
    # create a custom deduplication rule and delete it
    custom_rule = {
        "description": "Custom Rule",
        "provider_type": "datadog",
        "deduplication_fields": ["title", "message"],
        "default": False,
    }

    response = client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )
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

    assert response.status_code == 400


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
    custom_rule = {
        "description": "Full Deduplication Rule",
        "provider_type": "datadog",
        "deduplication_fields": ["title", "message", "source"],
        "default": False,
    }

    client.post(
        "/deduplications", json=custom_rule, headers={"x-api-key": "some-api-key"}
    )

    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()

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
            assert dedup_rule.get("dedup_ratio") == 66.67

    assert full_dedup_rule_found


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
    alert.pop("incident_id")
    alert.pop("group")
    alert.pop("title")

    client.post(
        "/alerts/event/datadog", json=alert, headers={"x-api-key": "some-api-key"}
    )

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

    deduplication_rules = client.get(
        "/deduplications", headers={"x-api-key": "some-api-key"}
    ).json()

    datadog_rule_found = False
    for dedup_rule in deduplication_rules:
        if dedup_rule.get("provider_type") == "datadog" and dedup_rule.get("default"):
            datadog_rule_found = True
            assert dedup_rule.get("ingested") == 3
            assert dedup_rule.get("dedup_ratio") == 66.67

    assert datadog_rule_found
