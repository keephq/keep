import pytest

from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    create_incident_from_dict,
)
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_add_remove_alert_to_incidents(
    db_session, client, test_app, setup_stress_alerts_no_elastic
):
    alerts = setup_stress_alerts_no_elastic(14)
    incident = create_incident_from_dict(
        "keep", {"user_generated_name": "test", "description": "test"}
    )
    valid_api_key = "valid_api_key"
    setup_api_key(db_session, valid_api_key)

    add_alerts_to_incident_by_incident_id(
        "keep", incident.id, [a.fingerprint for a in alerts]
    )

    response = client.get("/metrics?labels=a.b", headers={"X-API-KEY": "valid_api_key"})

    # Checking for alert_total metric
    assert (
        f'alerts_total{{incident_name="test",incident_id="{incident.id}",a_b=""}} 14'
        in response.text.split("\n")
    )

    # Checking for open_incidents_total metric
    assert "open_incidents_total 1" in response.text.split("\n")
