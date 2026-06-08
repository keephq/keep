import os
import pytest
from unittest.mock import patch, MagicMock
from keep.providers.squadcast_provider import SquadcastProvider
from keep.exceptions.provider import ProviderException

@pytest.fixture
def provider():
    return SquadcastProvider(api_key="dummy-token", api_url="https://api.squadcast.com/v3")

def test_validate_success(provider):
    with patch.object(provider.session, 'get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        provider.validate()
        mock_get.assert_called_with("https://api.squadcast.com/v3/users/me")

def test_validate_failure(provider):
    with patch.object(provider.session, 'get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_get.return_value = mock_resp
        with pytest.raises(ProviderException):
            provider.validate()

def test_list_services(provider):
    with patch.object(provider.session, 'get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"data": [{"id": "svc1", "name": "Service1"}]}
        mock_get.return_value = mock_resp
        services = provider.list_services()
        assert services == [{"id": "svc1", "name": "Service1"}]

def test_trigger_incident(provider):
    with patch.object(provider.session, 'post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"id": "inc1", "title": "Test Incident"}
        mock_post.return_value = mock_resp
        result = provider.trigger_incident("svc1", "Test Incident", "desc")
        assert result["id"] == "inc1"
        assert result["title"] == "Test Incident"

def test_list_incidents(provider):
    with patch.object(provider.session, 'get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"data": [{"id": "inc1", "status": "triggered"}]}
        mock_get.return_value = mock_resp
        incidents = provider.list_incidents(status="triggered")
        assert incidents == [{"id": "inc1", "status": "triggered"}]

def test_acknowledge_incident(provider):
    with patch.object(provider.session, 'post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"id": "inc1", "status": "acknowledged"}
        mock_post.return_value = mock_resp
        result = provider.acknowledge_incident("inc1")
        assert result["status"] == "acknowledged"

def test_resolve_incident(provider):
    with patch.object(provider.session, 'post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"id": "inc1", "status": "resolved"}
        mock_post.return_value = mock_resp
        result = provider.resolve_incident("inc1")
        assert result["status"] == "resolved"

def test_from_config_success():
    config = {"api_key": "abc123", "api_url": "https://api.squadcast.com/v3"}
    provider = SquadcastProvider.from_config(config)
    assert provider.api_key == "abc123"
    assert provider.api_url == "https://api.squadcast.com/v3"

def test_from_config_missing_key():
    config = {"api_url": "https://api.squadcast.com/v3"}
    with pytest.raises(ProviderException):
        SquadcastProvider.from_config(config)
