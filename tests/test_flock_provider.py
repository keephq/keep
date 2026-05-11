"""
Tests for Flock Provider
"""

import pytest
from unittest.mock import patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.flock_provider.flock_provider import FlockProvider
from keep.providers.models.provider_config import ProviderConfig


class TestFlockProvider:
    """Test cases for Flock Provider."""

    @pytest.fixture
    def context_manager(self):
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def flock_config(self):
        return ProviderConfig(
            description="Test Flock Provider",
            authentication={"webhook_url": "https://api.flock.com/hooks/sendMessage/abc123"},
        )

    @pytest.fixture
    def flock_provider(self, context_manager, flock_config):
        return FlockProvider(
            context_manager=context_manager,
            provider_id="test_flock_provider",
            config=flock_config,
        )

    @patch("requests.post")
    def test_send_message(self, mock_post, flock_provider):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"uid": "123", "text": "Test"}
        mock_post.return_value = mock_response

        result = flock_provider._notify(text="Test alert message")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.flock.com/hooks/sendMessage/abc123"
        assert call_args[1]["json"]["text"] == "Test alert message"
        assert result["text"] == "Test alert message"
        assert result["sent"] is True

    def test_missing_text_raises_error(self, flock_provider):
        with pytest.raises(Exception, match="text is required"):
            flock_provider._notify()

    def test_validate_config(self, flock_provider):
        flock_provider.validate_config()
        assert flock_provider.authentication_config.webhook_url == "https://api.flock.com/hooks/sendMessage/abc123"
