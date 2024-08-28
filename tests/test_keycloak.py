import pytest

from tests.fixtures.client import client, setup_api_key, test_app  # noqa


# sanity check with keycloak
@pytest.mark.parametrize("test_app", ["KEYCLOAK"], indirect=True)
def test_keycloak_sanity(keycloak_client, keycloak_token, client, test_app):
    """Tests the keycloak sanity check"""
    # Use the token to make a request to the Keep API
    headers = {"Authorization": f"Bearer {keycloak_token}"}
    response = client.get("/providers", headers=headers)
    assert response.status_code == 200
