# need to tests that:
# 1. On multiple tenants, the search mode is set to internal if elastic is disabled
# 2. On multiple tenants, the search mode is set to the tenant configuration
# 3. On single tenant, the search mode is set to elastic if elastic is enabled
# 4. On single tenant, the search mode is set to internal if elastic is disabled

import pytest

from keep.api.models.db.tenant import Tenant
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


@pytest.mark.parametrize("test_app", ["SINGLE_TENANT"], indirect=True)
def test_single_tenant_configuration_with_elastic(
    db_session, client, elastic_client, test_app
):
    valid_api_key = "valid_api_key"
    setup_api_key(db_session, valid_api_key)
    response = client.get("/preset/feed/alerts", headers={"x-api-key": valid_api_key})
    assert response.headers.get("x-search-type") == "elastic"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "SINGLE_TENANT",
            "ELASTIC_ENABLED": "false",
        },
    ],
    indirect=True,
)
def test_single_tenant_configuration_without_elastic(db_session, client, test_app):
    valid_api_key = "valid_api_key"
    setup_api_key(db_session, valid_api_key)
    response = client.get("/preset/feed/alerts", headers={"x-api-key": valid_api_key})
    assert response.headers.get("x-search-type") == "internal"


@pytest.mark.parametrize("test_app", ["MULTI_TENANT"], indirect=True)
def test_multi_tenant_configuration_with_elastic(
    db_session, client, elastic_client, test_app
):
    valid_api_key = "valid_api_key"
    valid_api_key_2 = "valid_api_key_2"
    db_session.add(
        Tenant(
            id="multi-tenant-id-1",
            name="multi-tenant-1",
        )
    )
    db_session.add(
        Tenant(
            id="multi-tenant-id-2",
            name="multi-tenant-2",
            configuration={"search_mode": "elastic"},
        )
    )
    setup_api_key(db_session, valid_api_key, tenant_id="multi-tenant-id-1")
    setup_api_key(db_session, valid_api_key_2, tenant_id="multi-tenant-id-2")
    response = client.get("/preset/feed/alerts", headers={"x-api-key": valid_api_key})
    assert response.headers.get("x-search-type") == "internal"

    response = client.get("/preset/feed/alerts", headers={"x-api-key": valid_api_key_2})
    assert response.headers.get("x-search-type") == "elastic"
