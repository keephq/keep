"""Tests for the SNMP provider's trap → AlertDto translation."""

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


class TestSnmpProvider:
    @pytest.fixture
    def context_manager(self):
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def provider(self, context_manager):
        return SnmpProvider(
            context_manager=context_manager,
            provider_id="snmp-test",
            config=ProviderConfig(authentication={"default_severity": "info"}),
        )

    def test_validate_config_defaults_when_empty(self, context_manager):
        provider = SnmpProvider(
            context_manager=context_manager,
            provider_id="snmp-no-auth",
            config=ProviderConfig(authentication={}),
        )
        assert provider.authentication_config.default_severity == "info"
        assert provider.authentication_config.community_string == "public"

    def test_standard_trap_oid_maps_to_known_name_and_severity(self, provider):
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source_address": "192.0.2.10",
        }
        alert = SnmpProvider._format_alert(event, provider_instance=provider)
        assert alert.name == "linkDown"
        assert alert.severity == AlertSeverity.HIGH.value
        assert alert.status == AlertStatus.FIRING.value
        assert alert.source == ["snmp"]
        assert alert.labels["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"

    def test_explicit_severity_overrides_trap_oid_default(self, provider):
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source_address": "192.0.2.10",
            "severity": "critical",
        }
        alert = SnmpProvider._format_alert(event, provider_instance=provider)
        assert alert.severity == AlertSeverity.CRITICAL.value

    def test_unknown_trap_falls_back_to_default_severity(self, context_manager):
        provider = SnmpProvider(
            context_manager=context_manager,
            provider_id="snmp-warn-default",
            config=ProviderConfig(authentication={"default_severity": "warning"}),
        )
        event = {
            "trap_oid": "1.3.6.1.4.1.99999.1",
            "source_address": "192.0.2.50",
            "trap_name": "vendorSpecificTrap",
        }
        alert = SnmpProvider._format_alert(event, provider_instance=provider)
        assert alert.name == "vendorSpecificTrap"
        assert alert.severity == AlertSeverity.WARNING.value

    def test_fingerprint_is_stable_for_same_oid_and_source(self, provider):
        event_a = {"trap_oid": "1.2.3", "source_address": "192.0.2.1"}
        event_b = {
            "trap_oid": "1.2.3",
            "source_address": "192.0.2.1",
            "variables": {"1.2.3.4": "different varbind"},
        }
        alert_a = SnmpProvider._format_alert(event_a, provider_instance=provider)
        alert_b = SnmpProvider._format_alert(event_b, provider_instance=provider)
        assert alert_a.fingerprint == alert_b.fingerprint

    def test_fingerprint_differs_for_different_source(self, provider):
        alert_a = SnmpProvider._format_alert(
            {"trap_oid": "1.2.3", "source_address": "192.0.2.1"},
            provider_instance=provider,
        )
        alert_b = SnmpProvider._format_alert(
            {"trap_oid": "1.2.3", "source_address": "192.0.2.2"},
            provider_instance=provider,
        )
        assert alert_a.fingerprint != alert_b.fingerprint

    def test_variables_are_exposed_as_prefixed_labels(self, provider):
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source_address": "192.0.2.10",
            "variables": {"1.3.6.1.2.1.2.2.1.1": "2"},
        }
        alert = SnmpProvider._format_alert(event, provider_instance=provider)
        assert alert.labels.get("var:1.3.6.1.2.1.2.2.1.1") == "2"

    def test_simulate_alert_returns_well_formed_payload(self):
        payload = SnmpProvider.simulate_alert(alert_type="linkDown")
        assert payload["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"
        assert payload["trap_name"] == "linkDown"

    def test_provider_type_is_snmp(self, provider):
        assert provider.provider_type == "snmp"

    def test_dispose_is_noop(self, provider):
        assert provider.dispose() is None
