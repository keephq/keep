import json
from uuid import UUID
import pytest
from keep.api.alert_deduplicator.deduplication_rules_provisioning import (
    provision_deduplication_rules_from_env,
)
from unittest.mock import patch
import keep.api.core.db
from keep.api.models.db.alert import AlertDeduplicationRule
from keep.api.models.provider import Provider
from keep.providers.providers_factory import ProvidersFactory


@pytest.fixture
def setup(monkeypatch):
    deduplication_rules_in_env_var = [
        {
            "name": "provisioned fake existing deduplication rule",
            "description": "new description",
            "provider_id": "p2b2c3d4e5f64789ab1234567890abcd",
            "provider_type": "prometheus",
            "fingerprint_fields": ["source"],
            "full_deduplication": True,
            "ignore_fields": ["ignore_field"],
        },
        {
            "name": "fake new deduplication rule",
            "description": "fake new deduplication rule description",
            "provider_id": "a1b2c3d4e5f64789ab1234567890abcd",
            "provider_type": "grafana",
            "fingerprint_fields": ["fingerprint"],
            "full_deduplication": False,
        },
    ]

    deduplication_rules_in_db = [
        AlertDeduplicationRule(
            id=UUID("f3a2b76c8430491da71684de9cf257ab"),
            name="provisioned fake existing deduplication rule",
            description="provisioned fake existing deduplication rule description",
            provider_id="edc4d65d53204cefb511321be98f748e",
            provider_type="prometheus",
            fingerprint_fields=["fingerprint", "source", "service"],
            full_deduplication=False,
            is_provisioned=True,
        ),
        AlertDeduplicationRule(
            id=UUID("a5d8f32b6c7049efb913c21da7e845fd"),
            name="provisioned fake deduplication rule to delete",
            description="fake new deduplication rule description",
            provider_id="a1b2c3d4e5f64789ab1234567890abcd",
            provider_type="grafana",
            fingerprint_fields=["fingerprint"],
            full_deduplication=False,
            is_provisioned=True,
        ),
        AlertDeduplicationRule(
            id=UUID("c7e3d28f95104b6a8f12dc45eb7639fa"),
            name="not provisioned fake deduplication rule",
            description="not provisioned fake deduplication rule",
            provider_id="a1b2c3d4e5f64789ab1234567890abcd",
            provider_type="grafana",
            fingerprint_fields=["fingerprint"],
            full_deduplication=False,
            is_provisioned=False,
        ),
    ]
    installed_providers = [
        Provider(
            id="edc4d65d53204cefb511321be98f748e",
            name="Installed Prometheus provider",
            display_name="Installed Prometheus provider",
            type="prometheus",
            enabled=True,
            can_query=True,
            can_notify=True,
        ),
        Provider(
            id="p2b2c3d4e5f64789ab1234567890abcd",
            name="Installed Prometheus provider second",
            display_name="Installed Prometheus provider",
            type="prometheus",
            enabled=True,
            can_query=True,
            can_notify=True,
        ),
    ]

    linked_providers = [
        Provider(
            id="a1b2c3d4e5f64789ab1234567890abcd",
            name="Linked Grafana provider",
            display_name="Linked Grafana provider",
            type="grafana",
            enabled=True,
            can_query=True,
            can_notify=True,
        )
    ]

    with patch(
        "keep.api.core.db.get_all_deduplication_rules",
        return_value=deduplication_rules_in_db,
    ) as mock_get_all, patch(
        "keep.api.core.db.delete_deduplication_rule", return_value=None
    ) as mock_delete, patch(
        "keep.api.core.db.update_deduplication_rule", return_value=None
    ) as mock_update, patch(
        "keep.api.core.db.create_deduplication_rule", return_value=None
    ) as mock_create, patch(
        "keep.providers.providers_factory.ProvidersFactory.get_installed_providers",
        return_value=installed_providers,
    ) as mock_get_providers, patch(
        "keep.providers.providers_factory.ProvidersFactory.get_linked_providers",
        return_value=linked_providers,
    ) as mock_get_linked_providers:

        fake_tenant_id = "fake_tenant_id"
        monkeypatch.setenv(
            "KEEP_DEDUPLICATION_RULES", json.dumps(deduplication_rules_in_env_var)
        )

        yield {
            "mock_get_all": mock_get_all,
            "mock_delete": mock_delete,
            "mock_update": mock_update,
            "mock_create": mock_create,
            "mock_get_providers": mock_get_providers,
            "mock_get_linked_providers": mock_get_linked_providers,
            "fake_tenant_id": fake_tenant_id,
            "deduplication_rules_in_env_var": deduplication_rules_in_env_var,
            "deduplication_rules_in_db": deduplication_rules_in_db,
            "linked_providers": linked_providers,
            "installed_providers": installed_providers,
        }


def test_provisioning_of_new_rule(setup):
    """
    Test the provisioning of new deduplication rules from the environment.
    """
    provision_deduplication_rules_from_env(setup["fake_tenant_id"])
    setup["mock_create"].assert_called_once_with(
        tenant_id=setup["fake_tenant_id"],
        name="fake new deduplication rule",
        description="fake new deduplication rule description",
        provider_id="a1b2c3d4e5f64789ab1234567890abcd",
        provider_type="grafana",
        created_by="system",
        enabled=True,
        fingerprint_fields=["fingerprint"],
        full_deduplication=False,
        ignore_fields=[],
        priority=0,
        is_provisioned=True,
    )


def test_provisioning_of_existing_rule(setup):
    """
    Test the provisioning of new deduplication rules from the environment.
    """
    provision_deduplication_rules_from_env(setup["fake_tenant_id"])
    setup["mock_update"].assert_called_once_with(
        tenant_id=setup["fake_tenant_id"],
        rule_id=str(UUID("f3a2b76c8430491da71684de9cf257ab")),
        name="provisioned fake existing deduplication rule",
        description="new description",
        provider_id="p2b2c3d4e5f64789ab1234567890abcd",
        provider_type="prometheus",
        last_updated_by="system",
        enabled=True,
        fingerprint_fields=["source"],
        full_deduplication=True,
        ignore_fields=["ignore_field"],
        priority=0,
    )


def test_deletion_of_provisioned_rule_not_in_env(setup):
    """
    Test the provisioning of new deduplication rules from the environment.
    """
    provision_deduplication_rules_from_env(setup["fake_tenant_id"])
    setup["mock_delete"].assert_called_once_with(
        tenant_id=setup["fake_tenant_id"],
        rule_id=str(UUID("a5d8f32b6c7049efb913c21da7e845fd")),
    )


def test_failing_validation_when_provisioned_rule_points_to_not_existing_provider(
    setup, monkeypatch
):
    monkeypatch.setenv(
        "KEEP_DEDUPLICATION_RULES",
        json.dumps(
            [
                {
                    "name": "fake rule",
                    "description": "pointing to not existing provider",
                    "provider_id": "f9a3c87d65204efbc712456be89f657d",
                    "provider_type": "prometheus",
                    "fingerprint_fields": [],
                    "full_deduplication": False,
                }
            ]
        ),
    )

    with pytest.raises(ValueError) as excinfo:
        provision_deduplication_rules_from_env(setup["fake_tenant_id"])

    assert (
        f"Deduplication rule with name 'fake rule' points to not existing provider of type 'prometheus' with id 'f9a3c87d65204efbc712456be89f657d'"
        in excinfo.value.args
    )
