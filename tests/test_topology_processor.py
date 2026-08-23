"""
Regression tests for TopologyProcessor._process_tenant scoping alerts per
application - see https://github.com/keephq/keep/issues/6701.

Before the fix, the tenant-wide services_to_alerts dict was passed straight
into _update_application_based_incident / _create_application_based_incident,
so an application's incident could pick up alerts belonging to services of a
completely different application. These tests mock out every DB-touching
collaborator so they run without a live database.
"""

from types import SimpleNamespace
from unittest.mock import patch

from keep.topologies.topology_processor import TopologyProcessor


def _make_application(name, service_names):
    return SimpleNamespace(
        name=name,
        id=name,
        services=[SimpleNamespace(service=s) for s in service_names],
    )


def _make_alert(service, fingerprint):
    return SimpleNamespace(service=service, fingerprint=fingerprint)


def _make_processor():
    # bypass __init__ (it wires up TenantConfiguration and other DB-backed
    # collaborators we don't need for this scoping logic)
    return object.__new__(TopologyProcessor)


def test_process_tenant_scopes_alerts_to_their_own_application():
    processor = _make_processor()
    processor.logger = __import__("logging").getLogger(__name__)

    app_a = _make_application("App A", ["service-a"])
    app_b = _make_application("App B", ["service-b"])

    alert_a = _make_alert("service-a", "fp-a")
    alert_b = _make_alert("service-b", "fp-b")

    with patch.object(
        processor,
        "_get_topology_data",
        return_value=[
            SimpleNamespace(service="service-a"),
            SimpleNamespace(service="service-b"),
        ],
    ), patch.object(
        processor, "_get_applications_data", return_value=[app_a, app_b]
    ), patch.object(
        processor, "_get_application_based_incident", return_value=None
    ), patch(
        "keep.topologies.topology_processor.get_last_alerts", return_value=[]
    ), patch(
        "keep.topologies.topology_processor.convert_db_alerts_to_dto_alerts",
        return_value=[alert_a, alert_b],
    ), patch.object(
        processor, "_create_application_based_incident"
    ) as create_incident_mock:
        processor._process_tenant("tenant-1")

    calls_by_app = {
        call.args[1].name: call.args[2] for call in create_incident_mock.call_args_list
    }

    assert set(calls_by_app["App A"].keys()) == {"service-a"}
    assert set(calls_by_app["App B"].keys()) == {"service-b"}


def test_process_tenant_scopes_alerts_when_updating_existing_incident():
    processor = _make_processor()
    processor.logger = __import__("logging").getLogger(__name__)

    app_a = _make_application("App A", ["service-a"])
    app_b = _make_application("App B", ["service-b"])
    existing_incident = SimpleNamespace(id="incident-a")

    alert_a = _make_alert("service-a", "fp-a")
    alert_b = _make_alert("service-b", "fp-b")

    def fake_get_incident(tenant_id, application):
        return existing_incident if application.name == "App A" else None

    with patch.object(
        processor,
        "_get_topology_data",
        return_value=[
            SimpleNamespace(service="service-a"),
            SimpleNamespace(service="service-b"),
        ],
    ), patch.object(
        processor, "_get_applications_data", return_value=[app_a, app_b]
    ), patch.object(
        processor, "_get_application_based_incident", side_effect=fake_get_incident
    ), patch(
        "keep.topologies.topology_processor.get_last_alerts", return_value=[]
    ), patch(
        "keep.topologies.topology_processor.convert_db_alerts_to_dto_alerts",
        return_value=[alert_a, alert_b],
    ), patch.object(
        processor, "_update_application_based_incident"
    ) as update_incident_mock, patch.object(
        processor, "_create_application_based_incident"
    ) as create_incident_mock:
        processor._process_tenant("tenant-1")

    # App A already has an incident -> update path, must only see service-a
    update_call = update_incident_mock.call_args_list[0]
    assert set(update_call.args[3].keys()) == {"service-a"}

    # App B has no incident yet -> create path, must only see service-b
    create_call = create_incident_mock.call_args_list[0]
    assert set(create_call.args[2].keys()) == {"service-b"}
