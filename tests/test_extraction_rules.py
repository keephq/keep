from time import sleep

import pytest
from isodate import parse_datetime

from tests.fixtures.client import client, setup_api_key, test_app  # noqa

VALID_API_KEY = "valid_api_key"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_create_extraction_rule(db_session, client, test_app):
    setup_api_key(db_session, VALID_API_KEY, role="webhook")

    # Try to create invalid extraction
    invalid_rule_dict = {}
    response = client.post(
        "/extraction", json=invalid_rule_dict, headers={"x-api-key": VALID_API_KEY}
    )
    assert response.status_code == 422

    valid_rule_dict = {
        "name": "rule",
        "attribute": "test",
        "regex": "(?P<test>.*)",
    }
    response = client.post(
        "/extraction", json=valid_rule_dict, headers={"x-api-key": VALID_API_KEY}
    )
    assert response.status_code == 200


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_extraction_rule_updated_at(db_session, client, test_app):
    setup_api_key(db_session, VALID_API_KEY, role="webhook")

    rule_dict = {
        "name": "rule",
        "attribute": "test",
        "regex": "(?P<test>.*)",
    }
    # Creating an extraction
    response = client.post(
        "/extraction", json=rule_dict, headers={"x-api-key": VALID_API_KEY}
    )
    assert response.status_code == 200

    response_data = response.json()

    assert "id" in response_data
    assert "updated_at" in response_data

    rule_id = response_data["id"]
    updated_at = parse_datetime(response_data["updated_at"])
    updated_rule_dict = {
        "name": "rule2",
        "attribute": "test",
        "regex": "(?P<test>.*)",
    }
    # Taking a deep breath before updating, to ensure updated_at will change
    # Without it update can happen in the same second, so we will not see any changes
    sleep(1)
    updated_response = client.put(
        f"/extraction/{rule_id}",
        json=updated_rule_dict,
        headers={"x-api-key": VALID_API_KEY},
    )

    assert updated_response.status_code == 200

    updated_response_data = updated_response.json()
    new_updated_at = parse_datetime(updated_response_data["updated_at"])

    assert new_updated_at > updated_at
