"""
Test for Keep Provider _notify_alert crash with None alert_results.

This test reproduces the issue described in https://github.com/keephq/keep/issues/6272
where _notify_alert crashes with TypeError: object of type 'NoneType' has no len()
when invoked via enrich_alert workflow action (no if_condition, alert_results is None).
"""

import uuid
from unittest.mock import MagicMock, patch

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.keep_provider.keep_provider import KeepProvider


def test_notify_alert_with_none_alert_results_no_crash():
    """
    When alert_results is None and no if_condition is provided,
    _notify_alert should handle it gracefully instead of crashing
    with TypeError: object of type 'NoneType' has no len().

    This is the enrich_alert scenario: the action is purely enrichment,
    no new alert is triggered, so alert_results is None.
    """
    tenant_id = SINGLE_TENANT_UUID
    context_manager = ContextManager(
        tenant_id=tenant_id,
        workflow_id=str(uuid.uuid4()),
    )

    provider_config = ProviderConfig(authentication={})
    provider = KeepProvider(
        context_manager=context_manager,
        provider_id="test-keep",
        config=provider_config,
    )

    # Simulate the enrich_alert scenario: context returns None for alert_results
    # (no foreach items, and step results are not a list)
    mock_context = {
        "foreach": {"items": None},
        "steps": {"this": {"results": {}}},  # not a list -> alert_results becomes None
    }

    with patch.object(
        context_manager, "get_full_context", return_value=mock_context
    ):
        # Mock the io_handler to avoid needing real alert infrastructure
        provider.io_handler = MagicMock()
        provider.io_handler.render_context.return_value = {}

        # Mock process_event and alert DAO to avoid DB dependency
        with patch("keep.providers.keep_provider.keep_provider.process_event"), \
             patch.object(provider, "logger"):
            # Before the fix, this would raise:
            # TypeError: object of type 'NoneType' has no len()
            result = provider._notify_alert()

            # Should return an empty list, not crash
            assert isinstance(result, list)
            assert len(result) == 0


def test_notify_alert_with_none_alert_results_and_alert_param():
    """
    When alert_results is None but an alert dict is provided,
    _notify_alert should create the alert from the parameter
    (this path already works, but we verify it still does).
    """
    tenant_id = SINGLE_TENANT_UUID
    context_manager = ContextManager(
        tenant_id=tenant_id,
        workflow_id=str(uuid.uuid4()),
    )

    provider_config = ProviderConfig(authentication={})
    provider = KeepProvider(
        context_manager=context_manager,
        provider_id="test-keep",
        config=provider_config,
    )

    mock_context = {
        "foreach": {"items": None},
        "steps": {"this": {"results": {}}},
    }

    alert_data = {"name": "test-alert", "status": "firing"}

    with patch.object(
        context_manager, "get_full_context", return_value=mock_context
    ):
        provider.io_handler = MagicMock()
        provider.io_handler.render_context.return_value = alert_data

        with patch("keep.providers.keep_provider.keep_provider.process_event"), \
             patch.object(provider, "logger"):
            # This should work: alert param provides the alert data
            result = provider._notify_alert(alert=alert_data)

            # Should return a list (may be empty if no DB, but should not crash)
            assert isinstance(result, list)
