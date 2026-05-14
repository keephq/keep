from copy import deepcopy

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.providers_factory import ProvidersFactory
from keep.providers.snmp_provider.alerts_mock import ALERTS
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


def test_link_down_maps_to_critical_firing():
    alert = SnmpProvider._format_alert(deepcopy(ALERTS["link_down"]["payload"]))

    assert alert.status == AlertStatus.FIRING.value
    assert alert.severity == AlertSeverity.CRITICAL.value
    assert alert.source == ["snmp"]
    assert alert.host == "10.0.0.15"
    assert alert.labels["ifDescr"] == "eth0"
    assert alert.labels["oid_1_3_6_1_2_1_2_2_1_2_1"] == "eth0"
    assert alert.trap_oid == "1.3.6.1.6.3.1.1.5.3"
    assert alert.lastReceived.startswith("2026-05-14T12:00:00")


def test_link_up_maps_to_resolved_info():
    alert = SnmpProvider._format_alert(deepcopy(ALERTS["link_up"]["payload"]))

    assert alert.status == AlertStatus.RESOLVED.value
    assert alert.severity == AlertSeverity.INFO.value
    assert alert.host == "router-1"
    assert alert.labels["oid_1_3_6_1_2_1_2_2_1_8_1"] == "up"


def test_auth_failure_maps_to_warning():
    alert = SnmpProvider._format_alert(
        deepcopy(ALERTS["authentication_failure"]["payload"])
    )

    assert alert.status == AlertStatus.FIRING.value
    assert alert.severity == AlertSeverity.WARNING.value
    assert alert.host == "core-switch-1"
    assert alert.generic_trap == "authenticationFailure"


def test_varbinds_accept_list_and_dict():
    list_payload = {
        "source": "switch-01",
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "varbinds": [
            ["1.3.6.1.2.1.2.2.1.2.2", "eth1"],
            {"oid": "1.3.6.1.2.1.2.2.1.8.2", "name": "ifOperStatus", "value": "down"},
        ],
    }
    dict_payload = {
        "source": "switch-01",
        "snmp_trap_oid": "1.3.6.1.6.3.1.1.5.4",
        "variable_bindings": {
            "1.3.6.1.2.1.2.2.1.2.2": "eth1",
            "1.3.6.1.2.1.2.2.1.8.2": "up",
        },
    }

    list_alert = SnmpProvider._format_alert(list_payload)
    dict_alert = SnmpProvider._format_alert(dict_payload)

    assert list_alert.labels["ifOperStatus"] == "down"
    assert list_alert.labels["oid_1_3_6_1_2_1_2_2_1_2_2"] == "eth1"
    assert dict_alert.labels["oid_1_3_6_1_2_1_2_2_1_8_2"] == "up"


def test_missing_fields_do_not_crash():
    alert = SnmpProvider._format_alert({})

    assert alert.status == AlertStatus.FIRING.value
    assert alert.severity == AlertSeverity.INFO.value
    assert alert.host == "unknown"
    assert alert.name == "SNMP SNMP Trap on unknown"
    assert alert.labels["snmp_host"] == "unknown"


def test_explicit_status_and_severity_are_normalized():
    payload = {
        "host": "router-2",
        "generic_trap": "enterpriseSpecific",
        "status": "ok",
        "severity": "crit",
    }

    alert = SnmpProvider._format_alert(payload)

    assert alert.status == AlertStatus.RESOLVED.value
    assert alert.severity == AlertSeverity.CRITICAL.value


def test_timestamp_aliases_and_unix_values_are_supported():
    alert = SnmpProvider._format_alert(
        {
            "host": "router-3",
            "generic_trap": "warmStart",
            "received_at": 1778760000,
        }
    )

    assert alert.lastReceived.startswith("2026-05-14T12:00:00")


def test_stable_id_is_derived_from_trap_identity():
    payload = {
        "host": "router-4",
        "generic_trap": "linkDown",
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "varbinds": [{"name": "ifDescr", "value": "eth0"}],
    }

    alert = SnmpProvider._format_alert(deepcopy(payload))
    repeated_alert = SnmpProvider._format_alert(deepcopy(payload))

    assert alert.id == repeated_alert.id
    assert alert.fingerprint == alert.id


def test_provider_factory_can_load_snmp():
    provider_class = ProvidersFactory.get_provider_class("snmp")

    assert provider_class is SnmpProvider


def test_provider_discovery_includes_snmp(monkeypatch):
    ProvidersFactory._loaded_providers_cache = None
    monkeypatch.setattr(
        "keep.providers.providers_factory.os.listdir", lambda _: ["snmp_provider"]
    )

    providers = ProvidersFactory.get_all_providers(ignore_cache_file=True)
    snmp_provider = next(provider for provider in providers if provider.type == "snmp")

    assert snmp_provider.display_name == "SNMP"
    assert snmp_provider.webhook_required is True
    assert snmp_provider.supports_webhook is True
    assert snmp_provider.docs_slug == "snmp-provider"


def test_simulate_alert_returns_example():
    simulated_alert = SnmpProvider.simulate_alert()

    assert isinstance(simulated_alert, dict)
    assert simulated_alert


def test_format_alert_accepts_batch_payload():
    alerts = SnmpProvider._format_alert(
        [
            deepcopy(ALERTS["link_down"]["payload"]),
            deepcopy(ALERTS["link_up"]["payload"]),
        ]
    )

    assert len(alerts) == 2
    assert alerts[0].status == AlertStatus.FIRING.value
    assert alerts[1].status == AlertStatus.RESOLVED.value
