"""
Tests for the 'correlate' deduplication rule type.

The 'correlate' rule computes a secondary correlation_fingerprint on each
alert without changing its primary fingerprint. When a subsequent alert
shares the same correlation_fingerprint as an existing alert in LastAlert,
it is flagged with is_correlated=True and correlated_to=<representative fingerprint>.
"""

import time
from datetime import datetime

import pytest

from keep.api.core.db import get_last_alert_by_correlation_fingerprint, get_last_alerts
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertStatus
from keep.api.models.db.alert import Alert, AlertDeduplicationRule, LastAlert
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_rule(db_session, rule_type, fingerprint_fields, name=None):
    """Insert an AlertDeduplicationRule directly into the test DB."""
    rule = AlertDeduplicationRule(
        name=name or f"Test {rule_type.capitalize()} Rule",
        description=f"Test {rule_type} rule",
        fingerprint_fields=fingerprint_fields,
        full_deduplication=False,
        ignore_fields=[],
        is_provisioned=False,
        tenant_id=SINGLE_TENANT_UUID,
        provider_id="test",
        provider_type="keep",
        last_updated_by="test",
        created_by="test",
        rule_type=rule_type,
    )
    db_session.add(rule)
    db_session.commit()
    return rule


def _alert_details(name, source="keep", **extra):
    """Build a details dict compatible with the create_alert fixture."""
    return {"name": name, "source": [source], **extra}


# ---------------------------------------------------------------------------
# Unit-level tests (use create_alert fixture + direct DB queries)
# ---------------------------------------------------------------------------


def test_correlation_fingerprint_computed(db_session, create_alert):
    """When a correlate rule exists, correlation_fingerprint is set on the stored alert."""
    _add_rule(db_session, "correlate", ["name"])

    create_alert("fp-cf-1", AlertStatus.FIRING, datetime.utcnow(), _alert_details("pod-alert"))

    alert = db_session.query(Alert).filter(Alert.fingerprint == "fp-cf-1").first()
    assert alert is not None
    assert alert.event.get("correlation_fingerprint") is not None


def test_correlation_fingerprint_stored_in_lastalert(db_session, create_alert):
    """After ingestion, LastAlert.correlation_fingerprint is populated and queryable."""
    _add_rule(db_session, "correlate", ["name"])

    create_alert("fp-la-1", AlertStatus.FIRING, datetime.utcnow(), _alert_details("pod-alert-la"))

    last_alert = db_session.query(LastAlert).filter(
        LastAlert.fingerprint == "fp-la-1"
    ).first()
    assert last_alert is not None
    assert last_alert.correlation_fingerprint is not None

    # The DB helper function should return the fingerprint for this correlation group
    rep = get_last_alert_by_correlation_fingerprint(
        SINGLE_TENANT_UUID, last_alert.correlation_fingerprint
    )
    assert rep == "fp-la-1"


def test_first_alert_in_group_not_correlated(db_session, create_alert):
    """The first alert in a correlation group has is_correlated=False and correlated_to=None."""
    _add_rule(db_session, "correlate", ["name"])

    create_alert("fp-first", AlertStatus.FIRING, datetime.utcnow(), _alert_details("same-alert"))

    alert = db_session.query(Alert).filter(Alert.fingerprint == "fp-first").first()
    assert alert.event.get("is_correlated") == False
    assert alert.event.get("correlated_to") is None


def test_second_alert_in_group_is_correlated(db_session, create_alert):
    """
    A second alert with the same correlation_fingerprint as an existing alert is
    flagged is_correlated=True and correlated_to=<first alert fingerprint>.
    """
    _add_rule(db_session, "correlate", ["name"])

    # First alert — becomes the representative of the correlation group
    create_alert("fp-rep", AlertStatus.FIRING, datetime.utcnow(), _alert_details("same-alert"))
    # Second alert — different fingerprint, same name → same correlation_fingerprint
    create_alert("fp-corr", AlertStatus.FIRING, datetime.utcnow(), _alert_details("same-alert"))

    rep = db_session.query(Alert).filter(Alert.fingerprint == "fp-rep").first()
    corr = db_session.query(Alert).filter(Alert.fingerprint == "fp-corr").first()

    assert rep.event.get("is_correlated") == False
    assert corr.event.get("is_correlated") == True
    assert corr.event.get("correlated_to") == "fp-rep"


def test_alerts_with_different_names_not_correlated(db_session, create_alert):
    """Two alerts with different names produce different correlation_fingerprints and are not correlated."""
    _add_rule(db_session, "correlate", ["name"])

    create_alert("fp-a", AlertStatus.FIRING, datetime.utcnow(), _alert_details("alert-alpha"))
    create_alert("fp-b", AlertStatus.FIRING, datetime.utcnow(), _alert_details("alert-beta"))

    a = db_session.query(Alert).filter(Alert.fingerprint == "fp-a").first()
    b = db_session.query(Alert).filter(Alert.fingerprint == "fp-b").first()

    assert a.event.get("is_correlated") == False
    assert b.event.get("is_correlated") == False
    assert a.event["correlation_fingerprint"] != b.event["correlation_fingerprint"]


def test_split_and_correlate_rules_are_independent(db_session, create_alert):
    """
    A split rule (overrides fingerprint) and a correlate rule (sets correlation_fingerprint)
    can coexist for the same provider. The split rule differentiates alerts by service,
    while the correlate rule groups them by name. Both Alert records are stored independently
    and the second is flagged as correlated to the first.
    """
    _add_rule(db_session, "split", ["service"])
    _add_rule(db_session, "correlate", ["name"])

    # Two alerts with different services (→ different split fingerprints) but same name
    create_alert(
        "fp-sc-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        _alert_details("shared-alertname", service="svc-a"),
    )
    create_alert(
        "fp-sc-2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        _alert_details("shared-alertname", service="svc-b"),
    )

    # Both alerts are stored as separate records
    assert db_session.query(Alert).count() == 2

    alerts = db_session.query(Alert).order_by(Alert.timestamp).all()
    first, second = alerts[0], alerts[1]

    # Both have a correlation_fingerprint (from the correlate rule)
    assert first.event.get("correlation_fingerprint") is not None
    assert second.event.get("correlation_fingerprint") is not None
    assert first.event["correlation_fingerprint"] == second.event["correlation_fingerprint"]

    # First alert is the representative; second is correlated to it
    assert first.event.get("is_correlated") == False
    assert second.event.get("is_correlated") == True
    assert second.event.get("correlated_to") == first.event["fingerprint"]


def test_resolved_representative_does_not_block_new_group(db_session, create_alert):
    """
    When the representative alert resolves, the next firing alert with the same
    correlation_fingerprint should start a fresh group (is_correlated=False), not
    be correlated to the stale resolved entry.
    """
    _add_rule(db_session, "correlate", ["name"])

    # First alert fires and becomes the representative
    create_alert("fp-old-rep", AlertStatus.FIRING, datetime.utcnow(), _alert_details("same-alert"))

    old_rep = db_session.query(Alert).filter(Alert.fingerprint == "fp-old-rep").first()
    assert old_rep.event.get("is_correlated") == False

    # The representative alert resolves
    create_alert("fp-old-rep", AlertStatus.RESOLVED, datetime.utcnow(), _alert_details("same-alert"))

    # A new alert with the same name fires — the resolved representative must NOT be returned
    create_alert("fp-new", AlertStatus.FIRING, datetime.utcnow(), _alert_details("same-alert"))

    new_alert = db_session.query(Alert).filter(Alert.fingerprint == "fp-new").first()
    assert new_alert.event.get("is_correlated") == False
    assert new_alert.event.get("correlated_to") is None


def test_no_correlate_rule_no_correlation_fingerprint(db_session, create_alert):
    """Without a correlate rule, correlation_fingerprint is not set on the alert."""
    # No correlate rule added

    create_alert("fp-no-rule", AlertStatus.FIRING, datetime.utcnow(), _alert_details("some-alert"))

    alert = db_session.query(Alert).filter(Alert.fingerprint == "fp-no-rule").first()
    assert alert is not None
    # correlation_fingerprint should be None (not set by the pipeline)
    assert alert.event.get("correlation_fingerprint") is None
    assert alert.event.get("is_correlated") == False


# ---------------------------------------------------------------------------
# Integration-level test (uses HTTP client)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "NOAUTH"}],
    indirect=True,
)
def test_correlate_rule_created_via_api(db_session, client, test_app):
    """Creating a rule via the API with rule_type='correlate' stores it correctly."""
    from keep.providers.providers_factory import ProvidersFactory

    # Register a linked provider by sending one alert first
    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()
    client.post(
        "/alerts/event/datadog",
        json=alert,
        headers={"x-api-key": "some-api-key"},
    )
    time.sleep(0.5)

    resp = client.post(
        "/deduplications",
        json={
            "name": "Pod Correlation Rule",
            "description": "Correlate pods by alertname",
            "provider_type": "datadog",
            "fingerprint_fields": ["name"],
            "full_deduplication": False,
            "ignore_fields": None,
            "rule_type": "correlate",
        },
        headers={"x-api-key": "some-api-key"},
    )
    assert resp.status_code == 200

    rules = client.get("/deduplications", headers={"x-api-key": "some-api-key"}).json()
    correlate_rule = next((r for r in rules if r["name"] == "Pod Correlation Rule"), None)
    assert correlate_rule is not None
    assert correlate_rule["rule_type"] == "correlate"


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "NOAUTH"}],
    indirect=True,
)
def test_split_rule_default_type(db_session, client, test_app):
    """A rule created without rule_type defaults to 'split'."""
    from keep.providers.providers_factory import ProvidersFactory

    provider = ProvidersFactory.get_provider_class("datadog")
    alert = provider.simulate_alert()
    client.post(
        "/alerts/event/datadog",
        json=alert,
        headers={"x-api-key": "some-api-key"},
    )
    time.sleep(0.5)

    resp = client.post(
        "/deduplications",
        json={
            "name": "Default Type Rule",
            "description": "Should default to split",
            "provider_type": "datadog",
            "fingerprint_fields": ["name"],
            "full_deduplication": False,
            "ignore_fields": None,
            # rule_type intentionally omitted
        },
        headers={"x-api-key": "some-api-key"},
    )
    assert resp.status_code == 200

    rules = client.get("/deduplications", headers={"x-api-key": "some-api-key"}).json()
    rule = next((r for r in rules if r["name"] == "Default Type Rule"), None)
    assert rule is not None
    assert rule["rule_type"] == "split"
