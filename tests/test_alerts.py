from datetime import datetime

import pytest

from keep.api.models.alert import AlertStatus
from tests.fixtures.client import client, test_app  # noqa


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_get_alert_by_fingerprint_preserves_calculated_started_at(
    db_session, client, test_app, create_alert
):
    timestamp = datetime.utcnow()
    fingerprint = "alert-with-calculated-started-at"
    create_alert(fingerprint, AlertStatus.FIRING, timestamp)

    response = client.get(f"/alerts/{fingerprint}", headers={"x-api-key": "some-key"})

    assert response.status_code == 200
    assert response.json()["startedAt"] == timestamp.isoformat(sep=" ")
