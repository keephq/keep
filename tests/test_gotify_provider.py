"""
Tests for Gotify Provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.gotify_provider.gotify_provider import GotifyProvider
from keep.providers.models.provider_config import ProviderConfig


class TestGotifyProvider:
    """Test cases for Gotify Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def gotify_config(self):
        """Create a test Gotify configuration."""
        return ProviderConfig(
            description="Test Gotify Provider",
            authentication={
                "url": "https://gotify.example.com",
                "token": "test_token_12345",
            },
        )

    @pytest.fixture
    def gotify_provider(self, context_manager, gotify_config):
        """Create a Gotify provider instance."""
        return GotifyProvider(
            context_manager=context_manager,
            provider_id="test_gotify_provider",
            config=gotify_config,
        )

    @patch("requests.post")
    def test_send_text_message(self, mock_post, gotify_provider):
        """Test sending a plain text message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "message": "Test alert message"}
        mock_post.return_value = mock_response

        # Send message
        result = gotify_provider._notify(message="Test alert message")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify URL
        assert call_args[0][0] == "https://gotify.example.com/message"

        # Verify headers
        assert call_args[1]["headers"]["X-Gotify-Key"] == "test_token_12345"

        # Verify payload
        assert call_args[1]["json"]["message"] == "Test alert message"
        assert call_args[1]["json"]["priority"] == 5

        # Verify return value
        assert result["message"] == "Test alert message"
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_message_with_title(self, mock_post, gotify_provider):
        """Test sending a message with a title."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "message": "Alert with title"}
        mock_post.return_value = mock_response

        # Send message with title
        result = gotify_provider._notify(
            message="Alert with title",
            title="Critical Alert",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload includes title
        assert call_args[1]["json"]["message"] == "Alert with title"
        assert call_args[1]["json"]["title"] == "Critical Alert"

        # Verify return value
        assert result["message"] == "Alert with title"
        assert result["title"] == "Critical Alert"

    @patch("requests.post")
    def test_send_message_with_priority(self, mock_post, gotify_provider):
        """Test sending a message with custom priority."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "message": "High priority alert"}
        mock_post.return_value = mock_response

        # Send message with high priority
        result = gotify_provider._notify(
            message="High priority alert",
            priority=10,
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload includes priority
        assert call_args[1]["json"]["message"] == "High priority alert"
        assert call_args[1]["json"]["priority"] == 10

        # Verify return value
        assert result["priority"] == 10

    @patch("requests.post")
    def test_url_trailing_slash(self, mock_post, gotify_provider):
        """Test that trailing slash on URL is handled correctly."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1}
        mock_post.return_value = mock_response

        # Update config with trailing slash
        gotify_provider.authentication_config.url = "https://gotify.example.com/"

        # Send message
        gotify_provider._notify(message="Test message")

        # Verify URL has no double slash
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://gotify.example.com/message"

    @patch("requests.post")
    def test_unauthorized_response(self, mock_post, gotify_provider):
        """Test handling of 401 unauthorized response."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="unauthorized - invalid token"):
            gotify_provider._notify(message="Test message")

    @patch("requests.post")
    def test_bad_request_response(self, mock_post, gotify_provider):
        """Test handling of 400 bad request response."""
        # Setup mock response for bad request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="bad request"):
            gotify_provider._notify(message="Test message")

    def test_missing_message_raises_error(self, gotify_provider):
        """Test that sending without a message raises an error."""
        with pytest.raises(Exception, match="message is required"):
            gotify_provider._notify()

    def test_validate_config(self, gotify_provider):
        """Test that configuration is validated correctly."""
        gotify_provider.validate_config()
        assert gotify_provider.authentication_config.url == "https://gotify.example.com"
        assert gotify_provider.authentication_config.token == "test_token_12345"

    @patch("requests.post")
    def test_validate_scopes_success(self, mock_post, gotify_provider):
        """Test successful scope validation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1}
        mock_post.return_value = mock_response

        result = gotify_provider.validate_scopes()
        assert result == {"send_message": True}

    @patch("requests.post")
    def test_validate_scopes_failure(self, mock_post, gotify_provider):
        """Test failed scope validation."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = gotify_provider.validate_scopes()
        assert "send_message" in result
        assert result["send_message"] != True
