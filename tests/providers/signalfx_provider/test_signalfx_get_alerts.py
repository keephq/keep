from unittest.mock import MagicMock, call, patch, sentinel

import pytest
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.signalfx_provider.signalfx_provider import SignalfxProvider


def _build_provider() -> SignalfxProvider:
    config = ProviderConfig(
        description="SignalFx Provider",
        authentication={"sf_token": "test-token"},
    )
    return SignalfxProvider(ContextManager(tenant_id="test"), "signalfx-test", config)


def _response(incidents):
    response = MagicMock()
    response.json.return_value = incidents
    return response


def test_empty_response_returns_empty_list():
    provider = _build_provider()
    response = _response([])

    with (
        patch("requests.get", return_value=response),
        patch.object(provider, "_format_alert_get_alert") as formatter,
    ):
        assert provider._get_alerts() == []

    response.raise_for_status.assert_called_once_with()
    formatter.assert_not_called()


def test_successful_incidents_return_all_formatted_alerts_in_order():
    provider = _build_provider()
    incidents = [{"incidentId": "first"}, {"incidentId": "second"}]
    response = _response(incidents)

    with (
        patch("requests.get", return_value=response),
        patch.object(
            provider,
            "_format_alert_get_alert",
            side_effect=[sentinel.first_alert, sentinel.second_alert],
        ) as formatter,
    ):
        alerts = provider._get_alerts()

    assert alerts == [sentinel.first_alert, sentinel.second_alert]
    assert formatter.call_args_list == [call(incidents[0]), call(incidents[1])]


def test_mixed_response_logs_failure_and_returns_successful_alerts():
    provider = _build_provider()
    incidents = [{"incidentId": "bad"}, {"incidentId": "good"}]
    response = _response(incidents)
    formatting_error = ValueError("malformed incident")

    with (
        patch("requests.get", return_value=response),
        patch.object(
            provider,
            "_format_alert_get_alert",
            side_effect=[formatting_error, sentinel.alert],
        ),
        patch.object(provider.logger, "error") as log_error,
    ):
        alerts = provider._get_alerts()

    assert alerts == [sentinel.alert]
    log_error.assert_called_once_with(
        "Failed to format SignalFx alert: malformed incident"
    )


def test_all_formatting_failures_raise_with_underlying_cause():
    provider = _build_provider()
    incidents = [{"incidentId": "first"}, {"incidentId": "second"}]
    response = _response(incidents)
    first_error = ValueError("first malformed incident")
    second_error = KeyError("second malformed incident")

    with (
        patch("requests.get", return_value=response),
        patch.object(
            provider,
            "_format_alert_get_alert",
            side_effect=[first_error, second_error],
        ),
        pytest.raises(RuntimeError) as exc_info,
    ):
        provider._get_alerts()

    assert str(exc_info.value) == "Failed to format any of 2 SignalFx incidents"
    assert exc_info.value.__cause__ is first_error


def test_http_error_propagates_before_formatting():
    provider = _build_provider()
    response = _response([{"incidentId": "unused"}])
    http_error = requests.exceptions.HTTPError("SignalFx unavailable")
    response.raise_for_status.side_effect = http_error

    with (
        patch("requests.get", return_value=response),
        patch.object(provider, "_format_alert_get_alert") as formatter,
        pytest.raises(requests.exceptions.HTTPError) as exc_info,
    ):
        provider._get_alerts()

    assert exc_info.value is http_error
    response.json.assert_not_called()
    formatter.assert_not_called()
