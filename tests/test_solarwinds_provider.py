"""Tests for the SolarWinds SWIS provider."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.solarwinds_provider.alerts_mock import (
    ACKNOWLEDGED_ALERT,
    ACTIVE_ALERT,
    ACTIVE_ALERTS,
    DOWN_NODE,
    DOWN_NODES,
    WARNING_ALERT,
    WARNING_NODE,
)
from keep.providers.solarwinds_provider.solarwinds_provider import (
    SolarwindsProvider,
    SolarwindsProviderAuthConfig,
)


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id="test", workflow_id="test")


@pytest.fixture
def provider_config():
    return ProviderConfig(
        description="SolarWinds test provider",
        authentication={
            "hostname": "orion.example.com",
            "username": "admin",
            "password": "secret",
            "port": 17778,
            "verify_ssl": False,
        },
    )


@pytest.fixture
def provider(context_manager, provider_config):
    p = SolarwindsProvider(
        context_manager=context_manager,
        provider_id="solarwinds-test",
        config=provider_config,
    )
    p.validate_config()
    return p


class TestSolarwindsProviderAuthConfig:
    def test_required_fields(self):
        config = SolarwindsProviderAuthConfig(
            hostname="orion.example.com",
            username="admin",
            password="secret",
        )
        assert config.hostname == "orion.example.com"
        assert config.username == "admin"
        assert config.password == "secret"
        assert config.port == 17778  # default
        assert config.verify_ssl is False  # default

    def test_custom_port(self):
        config = SolarwindsProviderAuthConfig(
            hostname="orion.example.com",
            username="admin",
            password="secret",
            port=443,
        )
        assert config.port == 443


class TestSolarwindsProviderInit:
    def test_provider_display_name(self):
        assert SolarwindsProvider.PROVIDER_DISPLAY_NAME == "SolarWinds"

    def test_provider_tags(self):
        assert "alert" in SolarwindsProvider.PROVIDER_TAGS

    def test_provider_category(self):
        assert "Monitoring" in SolarwindsProvider.PROVIDER_CATEGORY

    def test_validate_config(self, provider):
        assert provider.authentication_config.hostname == "orion.example.com"
        assert provider.authentication_config.port == 17778


class TestSolarwindsProviderBaseUrl:
    def test_base_url_formation(self, provider):
        url = provider._get_swis_base_url()
        assert "orion.example.com" in url
        assert "17778" in url
        assert "SolarWinds/InformationService/v3/Json" in url


class TestSolarwindsProviderSeverityMapping:
    def test_info_severity(self, provider):
        assert SolarwindsProvider.SEVERITY_MAP[1] == AlertSeverity.INFO

    def test_warning_severity(self, provider):
        assert SolarwindsProvider.SEVERITY_MAP[2] == AlertSeverity.WARNING

    def test_critical_severity(self, provider):
        assert SolarwindsProvider.SEVERITY_MAP[3] == AlertSeverity.CRITICAL

    def test_emergency_severity(self, provider):
        assert SolarwindsProvider.SEVERITY_MAP[4] == AlertSeverity.CRITICAL


class TestSolarwindsProviderGetActiveAlerts:
    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_get_active_alerts_success(self, mock_get, provider):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": ACTIVE_ALERTS}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        alerts = provider._get_active_alerts()

        assert len(alerts) == 3
        assert all(a.source == ["solarwinds"] for a in alerts)

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_firing_active_alert(self, mock_get, provider):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [ACTIVE_ALERT]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        alerts = provider._get_active_alerts()

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.id == str(ACTIVE_ALERT["AlertActiveID"])
        assert alert.name == ACTIVE_ALERT["Name"]
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL  # Severity 3 = CRITICAL
        assert alert.host == ACTIVE_ALERT["RelatedNodeCaption"]
        assert alert.acknowledged is False

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_acknowledged_alert_status(self, mock_get, provider):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [ACKNOWLEDGED_ALERT]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        alerts = provider._get_active_alerts()

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged is True
        assert alert.acknowledged_by == "admin"

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_warning_severity_mapping(self, mock_get, provider):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [WARNING_ALERT]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        alerts = provider._get_active_alerts()

        assert alerts[0].severity == AlertSeverity.WARNING  # Severity 2

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_empty_alerts(self, mock_get, provider):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        alerts = provider._get_active_alerts()

        assert len(alerts) == 0

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_connection_error_returns_empty(self, mock_get, provider):
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        # Should not raise, should log and return empty
        alerts = provider._get_active_alerts()
        assert alerts == []


class TestSolarwindsProviderGetNodeAlerts:
    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_get_node_alerts_success(self, mock_get, provider):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": DOWN_NODES}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        alerts = provider._get_node_alerts()

        assert len(alerts) == 2
        assert all(a.source == ["solarwinds"] for a in alerts)

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_down_node_is_critical_firing(self, mock_get, provider):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [DOWN_NODE]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        alerts = provider._get_node_alerts()

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert alert.host == "branch-router-02"
        assert alert.id == f"node-{DOWN_NODE['NodeID']}"

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_warning_node_is_warning_firing(self, mock_get, provider):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [WARNING_NODE]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        alerts = provider._get_node_alerts()

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING


class TestSolarwindsProviderGetAlerts:
    @patch.object(SolarwindsProvider, "_get_active_alerts")
    @patch.object(SolarwindsProvider, "_get_node_alerts")
    def test_get_alerts_combines_both(
        self, mock_nodes, mock_active, provider
    ):
        from keep.api.models.alert import AlertDto

        mock_active_alert = MagicMock(spec=AlertDto)
        mock_node_alert = MagicMock(spec=AlertDto)

        mock_active.return_value = [mock_active_alert]
        mock_nodes.return_value = [mock_node_alert]

        alerts = provider._get_alerts()

        assert len(alerts) == 2
        assert mock_active_alert in alerts
        assert mock_node_alert in alerts

    @patch.object(SolarwindsProvider, "_get_active_alerts")
    @patch.object(SolarwindsProvider, "_get_node_alerts")
    def test_get_alerts_handles_partial_failure(
        self, mock_nodes, mock_active, provider
    ):
        from keep.api.models.alert import AlertDto

        mock_active.side_effect = Exception("Active alerts query failed")
        mock_node_alert = MagicMock(spec=AlertDto)
        mock_nodes.return_value = [mock_node_alert]

        # Should not raise, should return node alerts
        alerts = provider._get_alerts()
        assert len(alerts) == 1


class TestSolarwindsProviderValidateScopes:
    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_valid_connection(self, mock_get, provider):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"NodeID": 1}]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        scopes = provider.validate_scopes()

        assert scopes["authenticated"] is True

    @patch(
        "keep.providers.solarwinds_provider.solarwinds_provider.requests.get"
    )
    def test_invalid_credentials(self, mock_get, provider):
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401 Unauthorized"
        )
        mock_get.return_value = mock_response

        scopes = provider.validate_scopes()

        assert scopes["authenticated"] is not True
        assert "401" in str(scopes["authenticated"])
