import asyncio
import importlib
import logging
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.client import client, test_app  # noqa


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"keepVictoriaMetrics":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234}}}',
        },
    ],
    indirect=True,
)
def test_provider_reprovisioning_with_updated_config(
    db_session, client, test_app, monkeypatch, caplog
):
    """
    Test that demonstrates provider reprovisioning with updated configuration.

    This test verifies that when a provider is reprovisioned with new configuration values,
    the updated configuration is correctly applied.
    """
    caplog.set_level(logging.DEBUG)

    # Step 1: Verify initial provider is provisioned
    response = client.get("/providers", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200

    providers = response.json()
    provisioned_providers = [
        p for p in providers.get("installed_providers") if p.get("provisioned")
    ]

    # Verify we have one provisioned provider
    assert len(provisioned_providers) == 1
    assert provisioned_providers[0]["type"] == "victoriametrics"
    assert (
        provisioned_providers[0]["details"]["authentication"]["VMAlertHost"]
        == "http://localhost"
    )

    # Step 2: Change environment variables to update provider configuration and mock reload
    updated_config = '{"keepVictoriaMetrics":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://vmmetrics.com","VMAlertPort":1234}}}'
    monkeypatch.setenv("KEEP_PROVIDERS", updated_config)

    with patch(
        "keep.providers.victoriametrics_provider.victoriametrics_provider.VictoriametricsProvider.validate_scopes",
        return_value={"connected": True},
    ):
        importlib.reload(sys.modules["keep.api.api"])

        from keep.api.api import get_app

        app = get_app()

        for event_handler in app.router.on_startup:
            asyncio.run(event_handler())

        from keep.api.config import provision_resources

        provision_resources()

        client = TestClient(app)

    # Step 3: Verify the provider was updated with new configuration
    response = client.get("/providers", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200

    providers = response.json()
    provisioned_providers = [
        p for p in providers.get("installed_providers") if p.get("provisioned")
    ]

    # Verify the updated configuration
    assert len(provisioned_providers) == 1
    assert provisioned_providers[0]["type"] == "victoriametrics"
    assert (
        provisioned_providers[0]["details"]["authentication"]["VMAlertHost"]
        == "http://vmmetrics.com"
    )
