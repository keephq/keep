from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.nagios_provider.nagios_provider import NagiosProvider


def make_provider() -> NagiosProvider:
    return NagiosProvider(
        ContextManager(tenant_id="singletenant", workflow_id="test"),
        provider_id="nagios",
        config=ProviderConfig(
            description="Nagios",
            authentication={
                "host_url": "https://nagios.example.com",
                "api_key": "secret",
            },
        ),
    )


def test_api_url_accepts_server_root_or_nagiosxi_base_path():
    provider = make_provider()

    assert (
        provider._api_url("objects/hoststatus")
        == "https://nagios.example.com/nagiosxi/api/v1/objects/hoststatus"
    )

    provider.authentication_config.host_url = "https://nagios.example.com/nagiosxi"
    assert (
        provider._api_url("objects/hoststatus")
        == "https://nagios.example.com/nagiosxi/api/v1/objects/hoststatus"
    )


def test_format_host_maps_down_to_critical_firing_alert():
    alert = NagiosProvider._format_host(
        {
            "hoststatus_id": "42",
            "host_name": "edge-router",
            "current_state": "1",
            "output": "PING CRITICAL - Packet loss = 100%",
            "last_check": 1_700_000_000,
        }
    )

    assert alert.id == "nagios-host-42"
    assert alert.name == "Nagios host edge-router"
    assert alert.status == AlertStatus.FIRING.value
    assert alert.severity == AlertSeverity.CRITICAL.value
    assert alert.source == ["nagios"]
    assert alert.fingerprint == "nagios-host-42"
    assert alert.labels["nagios_object_type"] == "host"


def test_format_service_maps_warning_acknowledged_status():
    alert = NagiosProvider._format_service(
        {
            "servicestatus_id": "87",
            "host_name": "api-01",
            "service_description": "CPU Load",
            "current_state": 1,
            "problem_acknowledged": "1",
            "output": "WARNING - load is high",
            "last_check": 1_700_000_000,
        }
    )

    assert alert.id == "nagios-service-87"
    assert alert.status == AlertStatus.ACKNOWLEDGED.value
    assert alert.severity == AlertSeverity.WARNING.value
    assert alert.labels["host_name"] == "api-01"
    assert alert.labels["service_description"] == "CPU Load"


@patch("keep.providers.nagios_provider.nagios_provider.requests.get")
def test_get_alerts_polls_hosts_and_services(mock_get):
    host_response = MagicMock(ok=True)
    host_response.json.return_value = {
        "hoststatus": [
            {
                "hoststatus_id": "1",
                "host_name": "db-01",
                "current_state": 0,
                "output": "UP",
                "last_check": 1_700_000_000,
            }
        ]
    }
    service_response = MagicMock(ok=True)
    service_response.json.return_value = {
        "servicestatus": [
            {
                "servicestatus_id": "2",
                "host_name": "db-01",
                "service_description": "Disk",
                "current_state": 2,
                "output": "CRITICAL - disk full",
                "last_check": 1_700_000_100,
            }
        ]
    }
    mock_get.side_effect = [host_response, service_response]

    alerts = make_provider()._get_alerts()

    assert [alert.id for alert in alerts] == ["nagios-host-1", "nagios-service-2"]
    assert alerts[0].status == AlertStatus.RESOLVED.value
    assert alerts[1].severity == AlertSeverity.CRITICAL.value
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0].kwargs["params"]["apikey"] == "secret"
    assert "objects/hoststatus" in mock_get.call_args_list[0].args[0]
    assert "objects/servicestatus" in mock_get.call_args_list[1].args[0]


@patch("keep.providers.nagios_provider.nagios_provider.requests.get")
def test_validate_scopes_reports_api_failure(mock_get):
    response = MagicMock(ok=False, status_code=401, text="Unauthorized")
    mock_get.return_value = response

    scopes = make_provider().validate_scopes()

    assert "read_status" in scopes
    assert "401" in scopes["read_status"]
