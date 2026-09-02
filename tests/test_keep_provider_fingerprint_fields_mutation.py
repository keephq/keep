"""
Test for KeepProvider._build_alert mutating the caller's fingerprint_fields list.

This reproduces the issue described in https://github.com/keephq/keep/issues/6719
where _build_alert calls fingerprint_fields.append("workflowId") on whatever list
was passed in. _notify_alert's per-alert loop passes the same fingerprint_fields
object into _build_alert on every iteration of a foreach batch, so each alert
after the first accumulates one more duplicate "workflowId" entry, which changes
its computed fingerprint.
"""

import uuid

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.keep_provider.keep_provider import KeepProvider
from keep.providers.models.provider_config import ProviderConfig


def _make_provider():
    context_manager = ContextManager(
        tenant_id=SINGLE_TENANT_UUID,
        workflow_id=str(uuid.uuid4()),
    )
    provider_config = ProviderConfig(authentication={})
    return KeepProvider(
        context_manager=context_manager,
        provider_id="test-keep",
        config=provider_config,
    )


def test_build_alert_does_not_mutate_caller_fingerprint_fields():
    """
    Calling _build_alert repeatedly with the same fingerprint_fields list -
    exactly what _notify_alert's per-alert loop does for a foreach batch -
    must not grow or otherwise mutate that list between calls.
    """
    provider = _make_provider()
    fingerprint_fields = ["labels.service"]

    for _ in range(3):
        provider._build_alert(
            {},
            fingerprint_fields,
            name="disk full",
            labels={"service": "db-primary"},
        )

    assert fingerprint_fields == ["labels.service"]


def test_build_alert_produces_consistent_fingerprints_across_a_batch():
    """
    Alerts that only differ in the value of the fingerprinted field should get
    fingerprints computed the same way, regardless of how many other alerts
    were built earlier in the same batch (same fingerprint_fields object reused,
    as _notify_alert does).
    """
    provider = _make_provider()
    fingerprint_fields = ["labels.service"]

    services = ["db-primary", "db-replica", "cache"]
    fingerprints = []
    for service in services:
        alert = provider._build_alert(
            {},
            fingerprint_fields,
            name="disk full",
            labels={"service": service},
        )
        fingerprints.append(alert.fingerprint)

    # Building the alert for "cache" independently (fresh fingerprint_fields,
    # as if it were the only/first alert in its own batch) must produce the
    # exact same fingerprint as when it was the 3rd alert in the loop above.
    standalone_alert = provider._build_alert(
        {},
        ["labels.service"],
        name="disk full",
        labels={"service": "cache"},
    )

    assert fingerprints[2] == standalone_alert.fingerprint
    # sanity: different services still produce different fingerprints
    assert len(set(fingerprints)) == len(services)
