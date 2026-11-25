import socket
from unittest.mock import MagicMock, patch

import pytest
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.mattermost_provider.mattermost_provider import MattermostProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.victoriametrics_provider.victoriametrics_provider import (
    VictoriametricsProvider,
)


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id="singletenant", workflow_id="test-timeouts")


def _mattermost_provider(
    context_manager, webhook_url="https://mattermost.example.com/hooks/test"
):
    config = ProviderConfig(
        id="mm-test",
        description="Mattermost Test Provider",
        authentication={"webhook_url": webhook_url},
    )
    return MattermostProvider(context_manager, provider_id="mm-test", config=config)


def _victoriametrics_provider(
    context_manager,
    vmalert_url="https://vmalert.example.com:8880",
    vmbackend_url="https://vmbackend.example.com:8428",
):
    config = ProviderConfig(
        id="vm-test",
        description="VictoriaMetrics Test Provider",
        authentication={
            "VMAlertURL": vmalert_url,
            "VMBackendURL": vmbackend_url,
        },
    )
    return VictoriametricsProvider(
        context_manager, provider_id="vm-test", config=config
    )


@patch("requests.post")
def test_mattermost_notify_passes_default_timeout(mock_post, context_manager):
    response = MagicMock(ok=True, text="ok")
    mock_post.return_value = response

    provider = _mattermost_provider(context_manager)
    provider.notify(message="hello")

    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["timeout"] == MattermostProvider.DEFAULT_TIMEOUT


@pytest.mark.parametrize(
    ("query_type", "expected_suffix", "json_payload"),
    [
        ("query", "/api/v1/query", {"data": {"result": [{"value": [1, "42"]}]}}),
        ("query_range", "/api/v1/query_range", {"data": {"result": []}}),
    ],
)
@patch("requests.get")
def test_victoriametrics_query_passes_default_timeout(
    mock_get, context_manager, query_type, expected_suffix, json_payload
):
    response = MagicMock(status_code=200)
    response.json.return_value = json_payload
    mock_get.return_value = response

    provider = _victoriametrics_provider(context_manager)
    provider.query(query="up", queryType=query_type, start="100", end="200", step="15s")

    mock_get.assert_called_once()
    assert mock_get.call_args.args[0].endswith(expected_suffix)
    assert (
        mock_get.call_args.kwargs["timeout"] == VictoriametricsProvider.DEFAULT_TIMEOUT
    )


@patch("requests.get")
def test_victoriametrics_scopes_alerts_and_scheme_probe_pass_default_timeout(
    mock_get, context_manager
):
    scopes_ok = MagicMock(status_code=200)
    alerts_ok = MagicMock(status_code=200)
    alerts_ok.json.return_value = {"data": {"alerts": []}}
    probe_ok = MagicMock(status_code=200)
    mock_get.side_effect = [scopes_ok, scopes_ok, alerts_ok, probe_ok, probe_ok]

    provider = _victoriametrics_provider(context_manager)
    assert provider.validate_scopes() == {"connected": True}
    assert provider._get_alerts() == []

    # Pre-scheme/unvalidated host configs trigger an HTTPS probe before caching the URL.
    provider._vmalert_host = None
    provider._vmbackend_host = None
    provider.authentication_config.VMAlertURL = None
    provider.authentication_config.VMBackendURL = None
    provider.authentication_config.VMAlertHost = "vmalert.local"
    provider.authentication_config.VMBackendHost = "vmbackend.local"
    assert provider.vmalert_host == "https://vmalert.local:8880"
    assert provider.vmbackend_host == "https://vmbackend.local:8428"

    assert mock_get.call_count == 5
    for call in mock_get.call_args_list:
        assert call.kwargs["timeout"] == VictoriametricsProvider.DEFAULT_TIMEOUT


@pytest.mark.parametrize(
    "kind", ["mattermost", "vm_query", "vm_query_range", "vm_alerts"]
)
def test_hung_server_raises_timeout_within_bounded_wait(
    context_manager, monkeypatch, kind
):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        url = f"http://127.0.0.1:{server.getsockname()[1]}"

        monkeypatch.setattr(MattermostProvider, "DEFAULT_TIMEOUT", (0.1, 0.1))
        monkeypatch.setattr(VictoriametricsProvider, "DEFAULT_TIMEOUT", (0.1, 0.1))

        if kind == "mattermost":
            provider = _mattermost_provider(
                context_manager, webhook_url=f"{url}/hooks/x"
            )
            with pytest.raises(requests.exceptions.Timeout):
                provider.notify(message="hi")
        else:
            provider = _victoriametrics_provider(
                context_manager, vmalert_url=url, vmbackend_url=url
            )
            with pytest.raises(requests.exceptions.Timeout):
                if kind == "vm_query":
                    provider.query(query="up", queryType="query")
                elif kind == "vm_query_range":
                    provider.query(query="up", queryType="query_range")
                else:
                    provider.get_alerts()
