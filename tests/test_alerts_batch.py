from datetime import datetime, timezone

import pytest

from keep.api.models.alert import AlertStatus


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_get_alerts_batch_by_fingerprints(
    db_session, client, test_app, create_alert
):
    timestamp = datetime.now(timezone.utc)
    create_alert("fp-batch-1", AlertStatus.FIRING, timestamp)
    create_alert("fp-batch-2", AlertStatus.FIRING, timestamp)

    response = client.post(
        "/alerts/batch",
        headers={"x-api-key": "some-key"},
        json=["fp-batch-1", "fp-batch-2", "fp-missing"],
    )

    assert response.status_code == 200
    results = response.json()
    returned_fingerprints = {alert["fingerprint"] for alert in results}
    assert returned_fingerprints == {"fp-batch-1", "fp-batch-2"}
