import os
import pytest

from keep.api.core.db import create_rule as create_rule_db
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


@pytest.mark.parametrize("test_app", ["MULTI_TENANT"], indirect=True)
def test_create_api_key(db_session, client, test_app):
    valid_api_key = "valid_api_key"
    setup_api_key(db_session, valid_api_key)
    new_api_key_data = {"name": "testkey", "role": "webhook"}
    response = client.post(
        "/settings/apikey", headers={"x-api-key": valid_api_key}, json=new_api_key_data
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["role"] == "webhook"
    assert response_data["secret"] is not None
    assert response_data["reference_id"] == "testkey"

    new_api_key_data = {"name": "testkey", "role": "webhook"}
    response_2 = client.post(
        "/settings/apikey", headers={"x-api-key": valid_api_key}, json=new_api_key_data
    )
    response_2_data = response_2.json()
    assert response_2.status_code == 400
    assert (
        response_2_data["detail"] == "Error creating API key: API key already exists."
    )
