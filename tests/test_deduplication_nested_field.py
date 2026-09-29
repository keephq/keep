"""
Tests for AlertDeduplicator._remove_field handling of nested ignore fields.

Reproduces and verifies the fix for https://github.com/keephq/keep/issues/6849:
- When a deduplication rule specifies an ignore_fields path with nested keys (e.g. labels.pod),
  alerts lacking that nested key must not raise KeyError and drop the alert.
- Multi-level nested field paths (e.g. labels.cluster.node) must preserve the parent
  dictionary structure and sibling attributes when removing the target field.
"""

from unittest.mock import MagicMock

from keep.api.alert_deduplicator.alert_deduplicator import AlertDeduplicator
from keep.api.models.alert import AlertDto


def test_remove_field_nested_existing_key():
    """Verify that an existing nested field is cleanly deleted from the alert attribute."""
    deduplicator = AlertDeduplicator(tenant_id="test-tenant")
    alert = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
        labels={"pod": "pod-123", "app": "payment", "env": "prod"},
    )

    result = deduplicator._remove_field("labels.pod", alert)

    assert "pod" not in result.labels
    assert result.labels["app"] == "payment"
    assert result.labels["env"] == "prod"


def test_remove_field_nested_missing_key_does_not_raise():
    """
    Issue #6849: Deduplication rule ignoring labels.pod must safely handle alerts
    where labels does not contain 'pod' without raising KeyError.
    """
    deduplicator = AlertDeduplicator(tenant_id="test-tenant")
    alert = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
        labels={"app": "payment", "env": "prod"},
    )

    # Must not raise KeyError: 'pod'
    result = deduplicator._remove_field("labels.pod", alert)

    assert result.labels == {"app": "payment", "env": "prod"}


def test_remove_field_nested_multi_level_preserves_parent_dict():
    """
    For depth > 2 (e.g. labels.cluster.node), removing the target field must preserve
    parent dict keys and sibling properties rather than overwriting the root attribute.
    """
    deduplicator = AlertDeduplicator(tenant_id="test-tenant")
    alert = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
        labels={
            "cluster": {
                "node": "worker-1",
                "zone": "us-east-1",
            },
            "service": "api",
        },
    )

    result = deduplicator._remove_field("labels.cluster.node", alert)

    assert result.labels["cluster"] == {"zone": "us-east-1"}
    assert result.labels["service"] == "api"


def test_remove_field_nested_missing_intermediate_dict():
    """If an intermediate key in the path does not exist, return alert safely."""
    deduplicator = AlertDeduplicator(tenant_id="test-tenant")
    alert = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
        labels={"service": "api"},
    )

    result = deduplicator._remove_field("labels.cluster.node", alert)

    assert result.labels == {"service": "api"}


def test_remove_field_non_dict_attribute():
    """If attribute is not a dict, return alert safely without error."""
    deduplicator = AlertDeduplicator(tenant_id="test-tenant")
    alert = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
        description="non-dict-string",
    )

    result = deduplicator._remove_field("description.nested", alert)

    assert result.description == "non-dict-string"


def test_remove_field_missing_top_level_attribute():
    """If top-level attribute does not exist on alert, return alert safely."""
    deduplicator = AlertDeduplicator(tenant_id="test-tenant")
    alert = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
    )

    result = deduplicator._remove_field("nonexistent.nested", alert)

    assert result.name == "test-alert"


def test_apply_deduplication_rule_with_nested_ignore_field_missing():
    """
    End-to-end verification of _apply_deduplication_rule with ignore_fields=["labels.pod"]
    when the alert has no 'pod' key.
    """
    deduplicator = AlertDeduplicator(tenant_id="test-tenant")
    rule = MagicMock(
        id="test-rule-id",
        name="Ignore pod",
        description="Ignore pod in labels",
        provider_type="keep",
        provider_id=None,
        fingerprint_fields=["name"],
        full_deduplication=True,
        ignore_fields=["labels.pod"],
    )
    alert = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
        labels={"service": "payment"},
    )

    # Must complete without KeyError and compute alert_hash
    deduplicator._apply_deduplication_rule(
        alert, rule, last_alert_fingerprint_to_hash={}
    )

    assert alert.alert_hash is not None
