import os
import pytest
from keep.providers.squadcast_provider import SquadcastProvider
from keep.exceptions.provider_exception import ProviderException

import responses

API_KEY = "test_api_key"
API_URL = "https://api.squadcast.com/v3"

@pytest.fixture
def provider():
    return SquadcastProvider(api_key=API_KEY)

def test_from_config():
    config = {"api_key": API_KEY}
    p = SquadcastProvider.from_config(config)
    assert isinstance(p, SquadcastProvider)
    assert p.api_key == API_KEY

    with pytest.raises(ProviderException):
        SquadcastProvider.from_config({})

@responses.activate
def test_list_services(provider):
    responses.add(
        responses.GET,
        f"{API_URL}/services",
        json=[{"id": "svc1", "name": "Service1"}],
        status=200
    )
    services = provider.list_services()
    assert isinstance(services, list)
    assert services[0]["id"] == "svc1"

@responses.activate
def test_list_incidents(provider):
    responses.add(
        responses.GET,
        f"{API_URL}/incidents",
        json=[{"id": "inc1", "status": "triggered"}],
        status=200
    )
    incidents = provider.list_incidents()
    assert isinstance(incidents, list)
    assert incidents[0]["id"] == "inc1"

@responses.activate
def test_create_incident(provider):
    responses.add(
        responses.POST,
        f"{API_URL}/incidents",
        json={"id": "inc2", "title": "Test Incident"},
        status=201
    )
    incident = provider.create_incident(service_id="svc1", title="Test Incident")
    assert incident["id"] == "inc2"

@responses.activate
def test_acknowledge_and_resolve_incident(provider):
    responses.add(
        responses.POST,
        f"{API_URL}/incidents/inc1/acknowledge",
        json={"id": "inc1", "status": "acknowledged"},
        status=200
    )
    responses.add(
        responses.POST,
        f"{API_URL}/incidents/inc1/resolve",
        json={"id": "inc1", "status": "resolved"},
        status=200
    )
    ack = provider.acknowledge_incident("inc1")
    assert ack["status"] == "acknowledged"
    res = provider.resolve_incident("inc1")
    assert res["status"] == "resolved"

@responses.activate
def test_get_incident(provider):
    responses.add(
        responses.GET,
        f"{API_URL}/incidents/inc1",
        json={"id": "inc1", "title": "Test Incident"},
        status=200
    )
    incident = provider.get_incident("inc1")
    assert incident["id"] == "inc1"

@responses.activate
def test_list_oncall_users(provider):
    responses.add(
        responses.GET,
        f"{API_URL}/schedules/sched1/oncall-users",
        json=[{"user_id": "u1", "name": "Alice"}],
        status=200
    )
    users = provider.list_oncall_users("sched1")
    assert users[0]["user_id"] == "u1"

@responses.activate
def test_request_error(provider):
    responses.add(
        responses.GET,
        f"{API_URL}/services",
        status=401
    )
    with pytest.raises(ProviderException):
        provider.list_services()
