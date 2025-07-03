import pytest
import time
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import text
from keep.api.api import get_app
from keep.api.models.alert import AlertDto
from tests.fixtures.client import client, setup_api_key, test_app  # noqa

@pytest.fixture
def client():
    app = get_app()
    return TestClient(app)

@pytest.fixture
def mock_alert_dto():
    return AlertDto(
        id="test_id",
        name="Test Alert",
        status="firing",
        severity="high",
        lastReceived="2021-01-01T00:00:00Z",
        source=["test_source"],
        fingerprint="mock_fingerprint",
        labels={},
    )

def seed_alert(client, alert_dto):
    response = client.post(
        "/alerts/event",
        headers={"x-api-key": "some-key"},
        json=alert_dto.dict(),
    )
    assert response.status_code == 202
    for _ in range(50):
        resp = client.get(
            f"/alerts/{alert_dto.fingerprint}", headers={"x-api-key": "some-key"}
        )
        if resp.status_code == 200:
            return
        time.sleep(0.1)
    pytest.fail("Alert not found after waiting")

def enrich_alert(client, fingerprint, enrichments):
    response = client.post(
        "/alerts/enrich",
        headers={"x-api-key": "some-key"},
        json={"fingerprint": fingerprint, "enrichments": enrichments},
    )
    assert response.status_code == 200

def get_enrichments(db_session, fingerprint):
    enrichment_row = db_session.execute(
        text("SELECT enrichments FROM alertenrichment WHERE alert_fingerprint = :fp"),
        {"fp": fingerprint}
    ).fetchone()
    assert enrichment_row is not None
    enrichments = enrichment_row[0]
    if isinstance(enrichments, str):
        import json
        enrichments = json.loads(enrichments)
    return enrichments

def trigger_cleanup(client):
    response = client.post(
        "/alerts/query",
        headers={"x-api-key": "some-key"},
        json={"limit": 10, "offset": 0},
    )
    assert response.status_code == 200

def assert_bool(val, expected: bool):
    """
    Assert that val is a boolean True/False (or its string representation).
    """
    if isinstance(val, bool):
        assert val is expected
    elif isinstance(val, str):
        assert val.lower() == str(expected).lower()
    else:
        pytest.fail(f"Value {val!r} is neither bool nor str for expected {expected!r}")

@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_dismissed_resets_and_fields_cleaned_when_until_expires(db_session, client, test_app, mock_alert_dto):
    """
    Regression test: When dismissedUntil expires,
    dismissed should be set to False (bool or equivalent string), dismissedUntil must be empty (""), and disposable_* fields removed.
    """
    seed_alert(client, mock_alert_dto)
    past_time = (datetime.utcnow() - timedelta(seconds=5)).isoformat(timespec='milliseconds') + "Z"
    enrich_alert(client, mock_alert_dto.fingerprint, {
        "dismissed": True,
        "dismissUntil": past_time,
        "disposable_dismissed": True,
        "disposable_dismissUntil": past_time,
    })
    trigger_cleanup(client)
    enrichment = get_enrichments(db_session, mock_alert_dto.fingerprint)
    # Should set dismissed = False
    assert_bool(enrichment.get("dismissed"), False)
    # Should set dismissedUntil to ""
    assert "dismissUntil" in enrichment, "dismissUntil should exist after expiry"
    assert enrichment.get("dismissUntil") == "", "dismissUntil should be empty string after expiry"
    # The disposable fields must be gone
    assert "disposable_dismissed" not in enrichment, "disposable_dismissed should be removed after expiry"
    assert "disposable_dismissUntil" not in enrichment, "disposable_dismissUntil should be removed after expiry"

@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_dismissed_persists_when_until_in_future(db_session, client, test_app, mock_alert_dto):
    """
    'dismissed' and related fields must remain if dismissedUntil is in the future.
    """
    seed_alert(client, mock_alert_dto)
    future_time = (datetime.utcnow() + timedelta(seconds=60)).isoformat(timespec='milliseconds') + "Z"
    enrich_alert(client, mock_alert_dto.fingerprint, {
        "dismissed": True,
        "dismissUntil": future_time,
        "disposable_dismissed": True,
        "disposable_dismissUntil": future_time,
    })
    trigger_cleanup(client)
    enrichment = get_enrichments(db_session, mock_alert_dto.fingerprint)
    assert_bool(enrichment.get("dismissed"), True)
    assert enrichment.get("dismissUntil") == future_time
    assert_bool(enrichment.get("disposable_dismissed"), True)
    assert enrichment.get("disposable_dismissUntil") == future_time