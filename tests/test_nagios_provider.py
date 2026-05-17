from unittest.mock import Mock, patch

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.nagios_provider.nagios_provider import NagiosProvider


def create_provider(host_url="https://nagios.example.com"):
    return NagiosProvider(
        context_manager=ContextManager(
            tenant_id="singletenant",
            workflow_id="test",
        ),
        provider_id="nagios-test",
        config=ProviderConfig(
            authentication={
                "host_url": host_url,
                "api_key": "test-api-key",
            }
        ),
    )


def mock_response(payload, ok=True, status_code=200, text="OK"):
    response = Mock()
    response.ok = ok
    response.status_code = status_code
    response.text = text
    response.json.return_value = payload
    return response


@patch("keep.providers.nagios_provider.nagios_provider.requests.get")
def test_get_alerts_polls_hosts_and_services(mock_get):
    mock_get.side_effect = [
        mock_response(
            {
                "hoststatus": [
                    {
                        "host_id": "101",
                        "host_name": "db-01",
                        "current_state": "1",
                        "plugin_output": "CRITICAL - host is down",
                        "last_check": 1710000000,
                        "problem_has_been_acknowledged": "0",
                    }
                ]
            }
        ),
        mock_response(
            {
                "servicestatus": [
                    {
                        "service_id": "202",
                        "host_name": "web-01",
                        "service_description": "HTTP",
                        "current_state": "1",
                        "plugin_output": "WARNING - latency is high",
                        "last_check": 1710000300,
                        "problem_has_been_acknowledged": "0",
                    }
                ]
            }
        ),
    ]

    alerts = create_provider()._get_alerts()

    assert len(alerts) == 2
    assert alerts[0].id == "nagios-host-101"
    assert alerts[0].status == AlertStatus.FIRING.value
    assert alerts[0].severity == AlertSeverity.CRITICAL.value
    assert alerts[0].labels["nagios_state"] == "DOWN"
    assert alerts[1].id == "nagios-service-202-HTTP"
    assert alerts[1].status == AlertStatus.FIRING.value
    assert alerts[1].severity == AlertSeverity.WARNING.value
    assert alerts[1].labels["nagios_state"] == "WARNING"
    assert mock_get.call_args_list[0].args[0] == (
        "https://nagios.example.com/nagiosxi/api/v1/objects/hoststatus"
    )
    assert mock_get.call_args_list[1].args[0] == (
        "https://nagios.example.com/nagiosxi/api/v1/objects/servicestatus"
    )
    assert mock_get.call_args_list[0].kwargs["params"] == {"apikey": "test-api-key"}


@patch("keep.providers.nagios_provider.nagios_provider.requests.get")
def test_host_unreachable_maps_to_critical_firing(mock_get):
    mock_get.side_effect = [
        mock_response(
            {
                "hoststatus": [
                    {
                        "host_id": "102",
                        "host_name": "cache-01",
                        "current_state": "2",
                        "plugin_output": "CRITICAL - host is unreachable",
                        "last_check": 1710000100,
                    }
                ]
            }
        ),
        mock_response({"servicestatus": []}),
    ]

    alerts = create_provider()._get_alerts()

    assert len(alerts) == 1
    assert alerts[0].id == "nagios-host-102"
    assert alerts[0].status == AlertStatus.FIRING.value
    assert alerts[0].severity == AlertSeverity.CRITICAL.value
    assert alerts[0].labels["nagios_state"] == "UNREACHABLE"
    assert alerts[0].name == "Nagios host cache-01 is UNREACHABLE"


@patch("keep.providers.nagios_provider.nagios_provider.requests.get")
def test_get_alerts_accepts_nagiosxi_base_url_and_single_object_response(mock_get):
    mock_get.side_effect = [
        mock_response(
            {
                "hoststatus": {
                    "host_id": "101",
                    "host_name": "db-01",
                    "current_state": 0,
                    "plugin_output": "OK - host is up",
                    "last_check": 1710000000,
                }
            }
        ),
        mock_response(
            {
                "servicestatus": {
                    "service_id": "202",
                    "host_name": "web-01",
                    "service_description": "HTTP",
                    "current_state": 3,
                    "plugin_output": "UNKNOWN - check timed out",
                    "last_check": 1710000300,
                }
            }
        ),
    ]

    alerts = create_provider("https://nagios.example.com/nagiosxi")._get_alerts()

    assert alerts[0].status == AlertStatus.RESOLVED.value
    assert alerts[0].severity == AlertSeverity.LOW.value
    assert alerts[1].status == AlertStatus.FIRING.value
    assert alerts[1].severity == AlertSeverity.INFO.value
    assert mock_get.call_args_list[0].args[0] == (
        "https://nagios.example.com/nagiosxi/api/v1/objects/hoststatus"
    )


@patch("keep.providers.nagios_provider.nagios_provider.requests.get")
def test_acknowledged_problem_maps_to_acknowledged_status(mock_get):
    mock_get.side_effect = [
        mock_response({"hoststatus": []}),
        mock_response(
            {
                "servicestatus": [
                    {
                        "service_id": "202",
                        "host_name": "web-01",
                        "service_description": "HTTP",
                        "current_state": 2,
                        "plugin_output": "CRITICAL - down",
                        "last_check": 1710000300,
                        "problem_has_been_acknowledged": "1",
                    }
                ]
            }
        ),
    ]

    alerts = create_provider()._get_alerts()

    assert len(alerts) == 1
    assert alerts[0].status == AlertStatus.ACKNOWLEDGED.value
    assert alerts[0].severity == AlertSeverity.CRITICAL.value
    assert alerts[0].acknowledged is True


@patch("keep.providers.nagios_provider.nagios_provider.requests.get")
def test_host_failure_does_not_block_service_alerts(mock_get):
    mock_get.side_effect = [
        mock_response({"error": "unauthorized"}, ok=False, status_code=401, text="no"),
        mock_response(
            {
                "servicestatus": [
                    {
                        "service_id": "202",
                        "host_name": "web-01",
                        "service_description": "HTTP",
                        "current_state": 2,
                        "plugin_output": "CRITICAL - down",
                        "last_check": 1710000300,
                    }
                ]
            }
        ),
    ]

    alerts = create_provider()._get_alerts()

    assert len(alerts) == 1
    assert alerts[0].id == "nagios-service-202-HTTP"


@patch("keep.providers.nagios_provider.nagios_provider.requests.get")
def test_validate_scopes_reports_authentication_result(mock_get):
    mock_get.return_value = mock_response({"hoststatus": []})

    assert create_provider().validate_scopes() == {"authenticated": True}
