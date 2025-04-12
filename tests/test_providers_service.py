from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from keep.providers.providers_service import ProvidersService


@pytest.fixture
def mock_db_session():
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.id = "test-provider-id"
    provider.type = "test-provider-type"
    provider.name = "test-provider"
    provider.tenant_id = "test-tenant-id"
    provider.provisioned = False
    return provider


@patch("keep.providers.providers_service.ContextManager")
@patch("keep.providers.providers_service.SecretManagerFactory")
@patch("keep.providers.providers_service.ProvidersFactory")
@patch("keep.providers.providers_service.EventSubscriber")
@patch("keep.providers.providers_service.select")
@patch("keep.providers.providers_service.get_all_deduplication_rules_by_provider")
@patch("keep.providers.providers_service.delete_deduplication_rule")
def test_delete_provider_cascade_deletes_deduplication_rules(
    mock_delete_deduplication_rule,
    mock_get_rules,
    mock_select,
    mock_event_subscriber,
    mock_providers_factory,
    mock_secret_manager_factory,
    mock_context_manager,
    mock_provider,
    mock_db_session,
):
    # Set up mocks
    mock_select_obj = MagicMock()
    mock_select.return_value = mock_select_obj
    mock_where_obj = MagicMock()
    mock_select_obj.where.return_value = mock_where_obj
    mock_db_session.exec.return_value.one_or_none.return_value = mock_provider

    # Set up deduplication rules
    mock_rule1 = MagicMock()
    mock_rule1.id = "rule-id-1"
    mock_rule1.name = "test-rule-1"

    mock_rule2 = MagicMock()
    mock_rule2.id = "rule-id-2"
    mock_rule2.name = "test-rule-2"

    mock_get_rules.return_value = [mock_rule1, mock_rule2]

    # Set up secret manager
    mock_secret_manager = MagicMock()
    mock_secret_manager_factory.get_secret_manager.return_value = mock_secret_manager

    # Create a provider and mock provider objects
    mock_provider_obj = MagicMock()
    mock_providers_factory.get_provider.return_value = mock_provider_obj

    # Call delete_provider
    ProvidersService.delete_provider(
        tenant_id="test-tenant-id",
        provider_id="test-provider-id",
        session=mock_db_session,
    )

    # Assert deduplication rules were fetched
    mock_get_rules.assert_called_once_with(
        "test-tenant-id", mock_provider.id, mock_provider.type
    )

    # Assert deduplication rules were deleted
    assert mock_delete_deduplication_rule.call_count == 2
    mock_delete_deduplication_rule.assert_any_call("rule-id-1", "test-tenant-id")
    mock_delete_deduplication_rule.assert_any_call("rule-id-2", "test-tenant-id")

    # Assert provider was deleted
    mock_db_session.delete.assert_called_once_with(mock_provider)
    mock_db_session.commit.assert_called_once()
