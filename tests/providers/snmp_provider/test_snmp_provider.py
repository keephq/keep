import json

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


def create_provider() -> SnmpProvider:
    return SnmpProvider(
        context_manager=ContextManager(tenant_id="test-tenant"),
        provider_id="snmp-test",
        config=ProviderConfig(authentication={}),
    )


def test_parse_event_raw_body_accepts_json_bytes_object():
    payload = {"trap_oid": "1.3.6.1.6.3.1.1.5.3", "source_address": "192.0.2.10"}
    parsed = SnmpProvider.parse_event_raw_body(json.dumps(payload).encode("utf-8"))
    assert parsed == payload


def test_parse_event_raw_body_accepts_json_bytes_array():
    payload = [
        {"trap_oid": "1.3.6.1.6.3.1.1.5.3", "source_address": "192.0.2.10"},
        {"trap_oid": "1.3.6.1.6.3.1.1.5.4", "source_address": "192.0.2.10"},
    ]
    parsed = SnmpProvider.parse_event_raw_body(json.dumps(payload).encode("utf-8"))
    assert parsed == payload


def test_parse_event_raw_body_passthrough_for_dict():
    payload = {"trap_oid": "1.3.6.1.6.3.1.1.5.5"}
    assert SnmpProvider.parse_event_raw_body(payload) is payload


def test_link_down_maps_to_critical_firing():
    alert = SnmpProvider._format_alert(
        {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source_address": "192.0.2.10",
            "variables": {"ifName": "xe-0/0/0"},
        }
    )
    assert alert.name == "linkDown"
    assert alert.severity == AlertSeverity.CRITICAL.value
    assert alert.status == AlertStatus.FIRING.value


def test_link_up_maps_to_info_firing():
    alert = SnmpProvider._format_alert(
        {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "source_address": "192.0.2.10",
            "variables": {"ifName": "xe-0/0/0"},
        }
    )
    assert alert.name == "linkUp"
    assert alert.severity == AlertSeverity.INFO.value
    assert alert.status == AlertStatus.FIRING.value


def test_unknown_oid_defaults_to_warning_firing():
    alert = SnmpProvider._format_alert(
        {
            "trap_oid": "1.3.6.1.4.1.8072.2.3.0.1",
            "source_address": "203.0.113.1",
        }
    )
    assert alert.name == "1.3.6.1.4.1.8072.2.3.0.1"
    assert alert.severity == AlertSeverity.WARNING.value
    assert alert.status == AlertStatus.FIRING.value


def test_missing_optional_fields_fall_back_cleanly():
    alert = SnmpProvider._format_alert({})
    assert alert.name == "SNMP Trap"
    assert alert.message == "SNMP Trap"
    assert alert.description == "SNMP Trap"
    assert alert.source == ["snmp"]
    assert alert.labels["trap_oid"] == ""
    assert alert.labels["source_address"] == ""


def test_explicit_fingerprint_is_used_as_is():
    alert = SnmpProvider._format_alert(
        {
            "trap_oid": "1.3.6.1.6.3.1.1.5.5",
            "source_address": "192.0.2.1",
            "fingerprint": "forwarder-managed-fingerprint",
        }
    )
    assert alert.fingerprint == "forwarder-managed-fingerprint"


def test_entity_id_participates_in_fingerprint():
    base_event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "source_address": "192.0.2.1",
    }
    first = SnmpProvider._format_alert({**base_event, "entity_id": "if-1"})
    second = SnmpProvider._format_alert({**base_event, "entity_id": "if-1"})
    third = SnmpProvider._format_alert({**base_event, "entity_id": "if-2"})

    assert first.fingerprint == second.fingerprint
    assert first.fingerprint != third.fingerprint


def test_entity_id_is_derived_from_ifindex_ifname_and_ifdescr():
    base_event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "source_address": "192.0.2.1",
    }

    ifindex_alert = SnmpProvider._format_alert(
        {**base_event, "variables": {"IF-MIB::ifIndex.2": "2"}}
    )
    ifname_alert = SnmpProvider._format_alert(
        {**base_event, "variables": {"ifName": "xe-0/0/0"}}
    )
    ifdescr_alert = SnmpProvider._format_alert(
        {**base_event, "variables": {"ifDescr": "uplink to core"}}
    )

    assert ifindex_alert.labels["entity_id"] == "2"
    assert ifname_alert.labels["entity_id"] == "xe-0/0/0"
    assert ifdescr_alert.labels["entity_id"] == "uplink to core"


def test_fingerprint_falls_back_to_source_and_oid():
    base_event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.1",
        "source_address": "198.51.100.10",
    }
    first = SnmpProvider._format_alert(base_event)
    second = SnmpProvider._format_alert(base_event)
    third = SnmpProvider._format_alert(
        {**base_event, "source_address": "198.51.100.11"}
    )

    assert first.fingerprint == second.fingerprint
    assert first.fingerprint != third.fingerprint


def test_provider_instantiates_without_auth_config():
    provider = create_provider()
    assert provider.PROVIDER_DISPLAY_NAME == "SNMP"
