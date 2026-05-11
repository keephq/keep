"""
Tests for Flock Provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.flock_provider.flock_provider import FlockProvider
from keep.providers.models.provider_config import ProviderConfig


class TestFlockProvider:
    """Test cases for Flock Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def flock_config(self):
        """Create a test Flock configuration."""
        return ProviderConfig(
            description="Test Flock Provider",
            authentication={
                "webhook_url": "https://api.flock.com/hooks/sendMessage/12345",
            },
        )

    @pytest.fixture
    def flock_provider(self, context_manager, flock_config):
        """Create a Flock provider instance."""
        return FlockProvider(
            context_manager=context_manager,
            provider_id="test_flock_provider",
            config=flock_config,
        )

    @patch("requests.post")
    def test_send_text_message(self, mock_post, flock_provider):
        """Test sending a plain text message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_post.return_value = mock_response

        # Send message
        result = flock_provider._notify(message="Test alert message")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Verify URL
        assert call_args[0][0] == "https://api.flock.com/hooks/sendMessage/12345"
        
        # Verify payload
        assert call_args[1]["json"]["text"] == "Test alert message"
        
        # Verify return value
        assert result["message"] == "Test alert message"
        assert result["status"] == 200
        assert result["sent"] is True

    @patch("requests.post")
    def test_unauthorized_response(self, mock_post, flock_provider):
        """Test handling of 401 unauthorized response."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Authentication failed"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="failed to send message"):
            flock_provider._notify(message="Test message")

    @patch("requests.post")
    def test_bad_request_response(self, mock_post, flock_provider):
        """Test handling of 400 bad request response."""
        # Setup mock response for bad request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="failed to send message"):
            flock_provider._notify(message="Test message")

    def test_missing_message_raises_error(self, flock_provider):
        """Test that sending without a message raises an error."""
        with pytest.raises(Exception, match="message is required"):
            flock_provider._notify()

    def test_validate_config(self, flock_provider):
        """Test that configuration is validated correctly."""
        flock_provider.validate_config()
        assert flock_provider.authentication_config.webhook_url == "https://api.flock.com/hooks/sendMessage/12345"

    @patch("requests.post")
    def test_validate_scopes_success(self, mock_post, flock_provider):
        """Test successful scope validation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_post.return_value = mock_response

        result = flock_provider.validate_scopes()
        assert result == {"send_message": True}

    @patch("requests.post")
    def test_validate_scopes_failure(self, mock_post, flock_provider):
        """Test failed scope validation."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = flock_provider.validate_scopes()
        assert "send_message" in result
        assert result["send_message"] != True
