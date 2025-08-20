import pytest
from datetime import datetime, timedelta
import pytz

from keep.api.models.alert import AlertStatus
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
def test_get_alert_by_fingerprint_success(db_session, client, test_app, create_alert):
    setup_api_key(db_session, "some-api-key")

    fingerprint = "unit-test-fp"
    now = datetime.now(tz=pytz.utc)
    create_alert(fingerprint, AlertStatus.FIRING, now - timedelta(minutes=1))

    response = client.get(
        f"/alerts/{fingerprint}", headers={"x-api-key": "some-api-key"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fingerprint"] == fingerprint
    assert body["status"].lower() == "firing"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_get_alert_by_fingerprint_not_found(db_session, client, test_app):
    setup_api_key(db_session, "some-api-key")

    response = client.get(
        "/alerts/non-existent-fp", headers={"x-api-key": "some-api-key"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Alert not found"


