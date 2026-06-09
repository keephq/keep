import pytest
import requests
import requests_mock
from keep.providers.squadcast_provider import SquadcastProvider
from keep.exceptions.provider import ProviderException

API_KEY = "test_api_key"
API_URL = "https://api.squadcast.com/v3"

@pytest.fixture
def provider():
    return SquadcastProvider(api_key=API_KEY)

def test_list_services(provider):
    with requests_mock.Mocker() as m:
        m.get(f"{API_URL}/services", json=[{"id": "svc1", "name": "Service1"}])
        services = provider.list_services()
        assert isinstance(services, list)
        assert services[0]["id"] == "svc1"

def test_list_incidents(provider):
    with requests_mock.Mocker() as m:
        m.get(f"{API_URL}/incidents", json=[{"id": "inc1", "status": "triggered"}])
        incidents = provider.list_incidents()
        assert isinstance(incidents, list)
        assert incidents[0]["id"] == "inc1"

def test_create_incident(provider):
    with requests_mock.Mocker() as m:
        m.post(f"{API_URL}/incidents", json={"id": "inc2", "title": "Test Incident"})
        result = provider.create_incident(service_id="svc1", title="Test Incident", message="Something happened")
        assert result["id"] == "inc2"
        assert result["title"] == "Test Incident"

def test_resolve_incident(provider):
    with requests_mock.Mocker() as m:
        m.post(f"{API_URL}/incidents/inc2/resolve", json={"id": "inc2", "status": "resolved"})
        result = provider.resolve_incident("inc2")
        assert result["status"] == "resolved"

def test_acknowledge_incident(provider):
    with requests_mock.Mocker() as m:
        m.post(f"{API_URL}/incidents/inc2/acknowledge", json={"id": "inc2", "status": "acknowledged"})
        result = provider.acknowledge_incident("inc2")
        assert result["status"] == "acknowledged"

def test_from_config():
    config = {"api_key": API_KEY}
    provider = SquadcastProvider.from_config(config)
    assert isinstance(provider, SquadcastProvider)
    assert provider.api_key == API_KEY

def test_missing_api_key():
    with pytest.raises(ProviderException):
        SquadcastProvider.from_config({})

def test_api_error(provider):
    with requests_mock.Mocker() as m:
        m.get(f"{API_URL}/services", status_code=401)
        with pytest.raises(ProviderException):
            provider.list_services()
