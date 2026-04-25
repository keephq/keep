import pytest
import responses
from unittest.mock import Mock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.solarwinds_provider.solarwinds_provider import SolarwindsProvider
from keep.providers.models.provider_config import ProviderConfig


@pytest.fixture
def solarwinds_provider():
    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "orion_hostname": "orion.example.com",
            "username": "admin",
            "password": "password",
            "port": 17778,
        },
        name="test-solarwinds",
    )
    provider = SolarwindsProvider(context_manager, "solarwinds", config)
    return provider


class TestSolarWindsProvider:
    @responses.activate
    def test_validate_scopes_success(self, solarwinds_provider):
        responses.add(
            responses.GET,
            "https://orion.example.com:17778/SolarWinds/InformationService/v3/Json/Query",
            json={"results": [{"1": 1}]},
            status=200,
        )

        scopes = solarwinds_provider.validate_scopes()
        assert scopes["alerts_read"] is True

    @responses.activate
    def test_validate_scopes_failure(self, solarwinds_provider):
        responses.add(
            responses.GET,
            "https://orion.example.com:17778/SolarWinds/InformationService/v3/Json/Query",
            json={},
            status=401,
        )

        scopes = solarwinds_provider.validate_scopes()
        assert "Failed: 401" in scopes["alerts_read"]

    @responses.activate
    def test_get_alerts_success(self, solarwinds_provider):
        mock_response = {
            "results": [
                {
                    "AlertID": 1,
                    "AlertObjectID": 101,
                    "Name": "CPU High",
                    "Message": "CPU usage is above 90%",
                    "Severity": "Critical",
                    "TriggerTimeStamp": "2024-01-01T10:00:00Z",
                    "LastExecutedTime": "2024-01-01T10:05:00Z",
                },
                {
                    "AlertID": 2,
                    "AlertObjectID": 102,
                    "Name": "Memory Warning",
                    "Message": "Memory usage is above 80%",
                    "Severity": "Warning",
                    "TriggerTimeStamp": "2024-01-01T11:00:00Z",
                    "LastExecutedTime": "2024-01-01T11:05:00Z",
                },
            ]
        }

        responses.add(
            responses.GET,
            "https://orion.example.com:17778/SolarWinds/InformationService/v3/Json/Query",
            json=mock_response,
            status=200,
        )

        alerts = solarwinds_provider._get_alerts()
        assert len(alerts) == 2
        assert alerts[0].name == "CPU High"
        assert alerts[0].severity.value == "critical"
        assert alerts[1].name == "Memory Warning"
        assert alerts[1].severity.value == "warning"

    @responses.activate
    def test_get_alerts_empty(self, solarwinds_provider):
        responses.add(
            responses.GET,
            "https://orion.example.com:17778/SolarWinds/InformationService/v3/Json/Query",
            json={"results": []},
            status=200,
        )

        alerts = solarwinds_provider._get_alerts()
        assert len(alerts) == 0

    @responses.activate
    def test_get_alerts_with_different_severities(self, solarwinds_provider):
        mock_response = {
            "results": [
                {
                    "AlertID": 1,
                    "Name": "Critical Alert",
                    "Message": "Critical issue",
                    "Severity": "Critical",
                    "TriggerTimeStamp": "2024-01-01T10:00:00Z",
                },
                {
                    "AlertID": 2,
                    "Name": "Serious Alert",
                    "Message": "Serious issue",
                    "Severity": "Serious",
                    "TriggerTimeStamp": "2024-01-01T10:00:00Z",
                },
                {
                    "AlertID": 3,
                    "Name": "Info Alert",
                    "Message": "Info message",
                    "Severity": "Informational",
                    "TriggerTimeStamp": "2024-01-01T10:00:00Z",
                },
            ]
        }

        responses.add(
            responses.GET,
            "https://orion.example.com:17778/SolarWinds/InformationService/v3/Json/Query",
            json=mock_response,
            status=200,
        )

        alerts = solarwinds_provider._get_alerts()
        assert len(alerts) == 3
        assert alerts[0].severity.value == "critical"
        assert alerts[1].severity.value == "high"
        assert alerts[2].severity.value == "info"
