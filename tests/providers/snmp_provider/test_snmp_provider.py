from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


def test_format_link_down_trap_from_list_varbinds():
    event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "source_ip": "10.0.0.12",
        "timestamp": "2026-05-13T08:15:00Z",
        "varbinds": [
            {
                "oid": "1.3.6.1.2.1.1.5.0",
                "name": "sysName",
                "value": "core-switch-1",
            },
            {
                "oid": "1.3.6.1.2.1.2.2.1.2.42",
                "name": "ifDescr",
                "value": "xe-0/0/42",
            },
        ],
    }

    alert = SnmpProvider._format_alert(event)

    assert alert.name == "SNMP linkDown"
    assert alert.status == AlertStatus.FIRING.value
    assert alert.severity == AlertSeverity.CRITICAL.value
    assert alert.source == ["snmp"]
    assert alert.hostname == "10.0.0.12"
    assert alert.varbinds["sysName"] == "core-switch-1"
    assert alert.varbinds["ifDescr"] == "xe-0/0/42"
    assert alert.labels == {
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "source_host": "10.0.0.12",
    }


def test_format_link_up_trap_resolves_alert():
    alert = SnmpProvider._format_alert(
        {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "agent_address": "10.0.0.12",
            "time": "2026-05-13T08:16:00Z",
            "varbinds": {"ifDescr": "xe-0/0/42"},
        }
    )

    assert alert.name == "SNMP linkUp"
    assert alert.status == AlertStatus.RESOLVED.value
    assert alert.severity == AlertSeverity.INFO.value
    assert alert.fingerprint == "snmp:10.0.0.12:1.3.6.1.6.3.1.1.5.4"


def test_format_custom_trap_respects_status_and_severity():
    alert = SnmpProvider._format_alert(
        {
            "name": "UPS battery low",
            "oid": "1.3.6.1.4.1.999.1",
            "hostname": "ups-1",
            "severity": "high",
            "status": "acknowledged",
            "message": "battery below threshold",
            "varbinds": [{"oid": "batteryPercent", "value": 12}],
        }
    )

    assert alert.name == "UPS battery low"
    assert alert.status == AlertStatus.ACKNOWLEDGED.value
    assert alert.severity == AlertSeverity.HIGH.value
    assert alert.message == "battery below threshold"
    assert alert.varbinds["batteryPercent"] == 12


def test_provider_factory_can_load_snmp_provider():
    provider_class = ProvidersFactory.get_provider_class("snmp")

    assert provider_class is SnmpProvider


def test_provider_config_allows_default_severity():
    provider = SnmpProvider(
        context_manager=ContextManager(
            tenant_id="singletenant",
            workflow_id="test",
        ),
        provider_id="snmp-test",
        config=ProviderConfig(
            description="SNMP test",
            authentication={"default_severity": "low"},
        ),
    )
    alert = SnmpProvider._format_alert(
        {
            "trap_oid": "1.3.6.1.4.1.999.2",
            "source_ip": "10.0.0.99",
        },
        provider,
    )

    assert alert.severity == AlertSeverity.LOW.value
