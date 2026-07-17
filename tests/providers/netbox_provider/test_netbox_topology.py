"""Tests for NetBox topology pulling (issue #3931).

The mapping tests exercise build_topology_services directly with NetBox API
payloads, the provider tests patch the HTTP layer and cover the webhook-only
backward compatibility, pagination and error handling of pull_topology.
"""

from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.netbox_provider.netbox_provider import (
    NetboxProvider,
    _rack_application_id,
    build_topology_services,
)

REQUESTS_GET = "keep.providers.netbox_provider.netbox_provider.requests.get"


def _device(id, name, site=None, rack=None, role=None, manufacturer=None, ip=None):
    return {
        "id": id,
        "name": name,
        "site": {"name": site} if site else None,
        "rack": rack,
        "role": {"name": role} if role else None,
        "device_type": (
            {"manufacturer": {"name": manufacturer}} if manufacturer else {}
        ),
        "primary_ip": {"address": ip} if ip else None,
        "description": "",
        "tags": [],
    }


def _cable(a_device, b_device):
    return {
        "a_terminations": [{"object": {"device": {"name": a_device}}}],
        "b_terminations": [{"object": {"device": {"name": b_device}}}],
    }


class TestBuildTopologyServices:
    def test_devices_become_services(self):
        devices = [
            _device(
                1,
                "sw-01",
                site="dc1",
                role="switch",
                manufacturer="Cisco",
                ip="10.0.0.1/24",
            )
        ]
        services = build_topology_services(devices, [], "netbox-1", "tenant/netbox-1")

        assert len(services) == 1
        service = services[0]
        assert service.service == "sw-01"
        assert service.display_name == "sw-01"
        assert service.source_provider_id == "netbox-1"
        assert service.ip_address == "10.0.0.1"
        assert service.category == "switch"
        assert service.manufacturer == "Cisco"
        assert service.namespace == "dc1"

    def test_unnamed_device_falls_back_to_id(self):
        services = build_topology_services(
            [_device(7, None)], [], "netbox-1", "tenant/netbox-1"
        )
        assert services[0].service == "device-7"

    def test_cables_become_dependencies(self):
        devices = [_device(1, "sw-01"), _device(2, "sw-02")]
        cables = [_cable("sw-01", "sw-02")]
        services = build_topology_services(
            devices, cables, "netbox-1", "tenant/netbox-1"
        )

        by_name = {service.service: service for service in services}
        assert by_name["sw-01"].dependencies == {"sw-02": "cable"}
        assert by_name["sw-02"].dependencies == {}

    def test_cable_to_unknown_device_is_skipped(self):
        devices = [_device(1, "sw-01")]
        cables = [_cable("sw-01", "not-in-netbox")]
        services = build_topology_services(
            devices, cables, "netbox-1", "tenant/netbox-1"
        )
        assert services[0].dependencies == {}

    def test_legacy_single_termination_cable(self):
        devices = [_device(1, "sw-01"), _device(2, "sw-02")]
        cables = [
            {
                "termination_a": {"device": {"name": "sw-01"}},
                "termination_b": {"device": {"name": "sw-02"}},
            }
        ]
        services = build_topology_services(
            devices, cables, "netbox-1", "tenant/netbox-1"
        )
        by_name = {service.service: service for service in services}
        assert by_name["sw-01"].dependencies == {"sw-02": "cable"}

    def test_racks_not_grouped_by_default(self):
        devices = [_device(1, "sw-01", rack={"id": 3, "name": "R1"})]
        services = build_topology_services(devices, [], "netbox-1", "tenant/netbox-1")
        assert services[0].application_relations is None

    def test_racks_grouped_as_applications_when_enabled(self):
        rack = {"id": 3, "name": "R1"}
        devices = [
            _device(1, "sw-01", rack=rack),
            _device(2, "sw-02", rack=rack),
            _device(3, "sw-03"),
        ]
        services = build_topology_services(
            devices, [], "netbox-1", "tenant/netbox-1", group_racks_as_applications=True
        )

        by_name = {service.service: service for service in services}
        rack_id = _rack_application_id("tenant/netbox-1", 3)
        assert by_name["sw-01"].application_relations == {rack_id: "Rack R1"}
        assert by_name["sw-02"].application_relations == {rack_id: "Rack R1"}
        assert by_name["sw-03"].application_relations is None

    def test_rack_application_id_is_stable_and_namespaced(self):
        assert _rack_application_id("t1/p1", 3) == _rack_application_id("t1/p1", 3)
        assert _rack_application_id("t1/p1", 3) != _rack_application_id("t2/p1", 3)
        assert _rack_application_id("t1/p1", 3) != _rack_application_id("t1/p1", 4)


def _make_provider(**auth):
    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(authentication=auth or None, name="test-netbox")
    return NetboxProvider(context_manager, "netbox-1", config)


def _response(json_data, ok=True, status_code=200):
    response = MagicMock()
    response.ok = ok
    response.status_code = status_code
    response.json.return_value = json_data
    return response


class TestPullTopology:
    def test_webhook_only_install_is_a_noop(self):
        provider = _make_provider()
        with patch(REQUESTS_GET) as mock_get:
            services, applications = provider.pull_topology()
        assert services == []
        assert applications == {}
        mock_get.assert_not_called()

    def test_webhook_only_install_validates_scopes(self):
        provider = _make_provider()
        assert provider.validate_scopes() == {"authenticated": True}

    def test_pulls_devices_and_cables(self):
        provider = _make_provider(url="https://netbox.example.com", api_token="token")
        responses = [
            _response(
                {"results": [_device(1, "sw-01"), _device(2, "sw-02")], "next": None}
            ),
            _response({"results": [_cable("sw-01", "sw-02")], "next": None}),
        ]
        with patch(REQUESTS_GET, side_effect=responses) as mock_get:
            services, _ = provider.pull_topology()

        assert {service.service for service in services} == {"sw-01", "sw-02"}
        urls = [call.args[0] for call in mock_get.call_args_list]
        assert urls == [
            "https://netbox.example.com/api/dcim/devices/",
            "https://netbox.example.com/api/dcim/cables/",
        ]
        for call in mock_get.call_args_list:
            assert call.kwargs["headers"] == {"Authorization": "Token token"}
            assert call.kwargs["timeout"] == NetboxProvider.REQUEST_TIMEOUT

    def test_follows_pagination(self):
        provider = _make_provider(url="https://netbox.example.com", api_token="token")
        responses = [
            _response({"results": [_device(1, "sw-01")], "next": "page2"}),
            _response({"results": [_device(2, "sw-02")], "next": None}),
            _response({"results": [], "next": None}),
        ]
        with patch(REQUESTS_GET, side_effect=responses) as mock_get:
            services, _ = provider.pull_topology()

        assert {service.service for service in services} == {"sw-01", "sw-02"}
        offsets = [
            call.kwargs["params"]["offset"] for call in mock_get.call_args_list[:2]
        ]
        assert offsets == [0, 1000]

    def test_max_devices_caps_the_pull(self):
        provider = _make_provider(
            url="https://netbox.example.com", api_token="token", max_devices=2
        )
        responses = [
            _response(
                {
                    "results": [_device(1, "sw-01"), _device(2, "sw-02")],
                    "next": "page2",
                }
            ),
            _response({"results": [], "next": None}),
        ]
        with patch(REQUESTS_GET, side_effect=responses):
            services, _ = provider.pull_topology()
        assert len(services) == 2

    def test_api_error_raises(self):
        provider = _make_provider(url="https://netbox.example.com", api_token="token")
        with patch(REQUESTS_GET, return_value=_response({}, ok=False, status_code=403)):
            with pytest.raises(ProviderException):
                provider.pull_topology()

    def test_verify_is_wired_through(self):
        provider = _make_provider(
            url="https://netbox.example.com", api_token="token", verify=False
        )
        responses = [
            _response({"results": [], "next": None}),
            _response({"results": [], "next": None}),
        ]
        with patch(REQUESTS_GET, side_effect=responses) as mock_get:
            provider.pull_topology()
        for call in mock_get.call_args_list:
            assert call.kwargs["verify"] is False


class TestProcessTopologyIntegration:
    def _pull(self, provider):
        rack = {"id": 3, "name": "R1"}
        responses = [
            _response(
                {
                    "results": [
                        _device(1, "sw-01", rack=rack),
                        _device(2, "sw-02", rack=rack),
                    ],
                    "next": None,
                }
            ),
            _response({"results": [_cable("sw-01", "sw-02")], "next": None}),
        ]
        with patch(REQUESTS_GET, side_effect=responses):
            services, _ = provider.pull_topology()
        return services

    def test_pulled_topology_is_processed_and_repull_is_idempotent(self, db_session):
        from keep.api.core.dependencies import SINGLE_TENANT_UUID
        from keep.api.models.db.topology import TopologyApplication, TopologyService
        from keep.api.tasks.process_topology_task import process_topology
        from sqlmodel import Session, select

        import keep.api.core.db as db

        context_manager = ContextManager(
            tenant_id=SINGLE_TENANT_UUID, workflow_id="test"
        )
        provider = NetboxProvider(
            context_manager,
            "netbox-1",
            ProviderConfig(
                authentication={
                    "url": "https://netbox.example.com",
                    "api_token": "token",
                    "group_racks_as_applications": True,
                },
                name="test-netbox",
            ),
        )

        for _ in range(2):
            services = self._pull(provider)
            process_topology(SINGLE_TENANT_UUID, services, "netbox-1", "netbox")

        with Session(db.engine) as session:
            db_services = session.exec(
                select(TopologyService).where(
                    TopologyService.tenant_id == SINGLE_TENANT_UUID
                )
            ).all()
            db_applications = session.exec(
                select(TopologyApplication).where(
                    TopologyApplication.tenant_id == SINGLE_TENANT_UUID
                )
            ).all()

            assert {service.service for service in db_services} == {"sw-01", "sw-02"}
            by_name = {service.service: service for service in db_services}
            assert by_name["sw-01"].source_provider_id == "netbox-1"
            assert [
                dependency.depends_on_service_id
                for dependency in by_name["sw-01"].dependencies
            ] == [by_name["sw-02"].id]

            assert len(db_applications) == 1
            assert db_applications[0].name == "Rack R1"
            assert db_applications[0].id == _rack_application_id(
                f"{SINGLE_TENANT_UUID}/netbox-1", 3
            )


class TestWebhookAlertFormat:
    def test_format_alert_unchanged(self):
        event = {
            "timestamp": "2025-01-01T00:00:00Z",
            "model": "device",
            "username": "admin",
            "request_id": "abc",
            "event": "updated",
            "data": {"name": "sw-01", "created": "2024-01-01T00:00:00Z"},
            "snapshots": {},
        }
        alert = NetboxProvider._format_alert(event)
        assert alert.name == "sw-01"
        assert alert.source == ["netbox"]
