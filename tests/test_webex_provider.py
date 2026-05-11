"""
Tests for Cisco Webex Provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.webex_provider.webex_provider import WebexProvider
from keep.providers.models.provider_config import ProviderConfig


class TestWebexProvider:
    """Test cases for Cisco Webex Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def webex_config(self):
        """Create a test Webex configuration."""
        return ProviderConfig(
            description="Test Webex Provider",
            authentication={
                "access_token": "test_access_token_12345",
            },
        )

    @pytest.fixture
    def webex_provider(self, context_manager, webex_config):
        """Create a Webex provider instance."""
        return WebexProvider(
            context_manager=context_manager,
            provider_id="test_webex_provider",
            config=webex_config,
        )

    @patch("requests.post")
    def test_send_text_message_to_room(self, mock_post, webex_provider):
        """Test sending a plain text message to a room."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_123", "text": "Test alert message"}
        mock_post.return_value = mock_response

        # Send message
        result = webex_provider._notify(message="Test alert message", roomId="room_123")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify URL
        assert call_args[0][0] == "https://webexapis.com/v1/messages"

        # Verify headers
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_access_token_12345"
        assert call_args[1]["headers"]["Content-Type"] == "application/json"

        # Verify payload
        assert call_args[1]["json"]["roomId"] == "room_123"
        assert call_args[1]["json"]["text"] == "Test alert message"

        # Verify return value
        assert result["message"] == "Test alert message"
        assert result["id"] == "msg_123"
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_message_to_person_email(self, mock_post, webex_provider):
        """Test sending a message to a person by email."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_456", "text": "Direct message"}
        mock_post.return_value = mock_response

        # Send message
        result = webex_provider._notify(
            message="Direct message",
            toPersonEmail="user@example.com",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload
        assert call_args[1]["json"]["toPersonEmail"] == "user@example.com"
        assert call_args[1]["json"]["text"] == "Direct message"

        # Verify return value
        assert result["message"] == "Direct message"
        assert result["id"] == "msg_456"
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_markdown_message(self, mock_post, webex_provider):
        """Test sending a markdown-formatted message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_789", "markdown": "**Bold alert**"}
        mock_post.return_value = mock_response

        # Send message with markdown
        result = webex_provider._notify(
            message="Alert",
            roomId="room_123",
            markdown="**Bold alert**",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload
        assert call_args[1]["json"]["roomId"] == "room_123"
        assert call_args[1]["json"]["markdown"] == "**Bold alert**"
        # text should not be present when markdown is provided
        assert "text" not in call_args[1]["json"]

        # Verify return value
        assert result["message"] == "Alert"
        assert result["id"] == "msg_789"
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_message_to_person_id(self, mock_post, webex_provider):
        """Test sending a message to a person by ID."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_abc", "text": "Person ID message"}
        mock_post.return_value = mock_response

        # Send message
        result = webex_provider._notify(
            message="Person ID message",
            toPersonId="person_123",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload
        assert call_args[1]["json"]["toPersonId"] == "person_123"
        assert call_args[1]["json"]["text"] == "Person ID message"

        # Verify return value
        assert result["message"] == "Person ID message"
        assert result["id"] == "msg_abc"
        assert result["sent"] is True

    @patch("requests.post")
    def test_unauthorized_response(self, mock_post, webex_provider):
        """Test handling of 401 unauthorized response."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="unauthorized - invalid access token"):
            webex_provider._notify(message="Test message", roomId="room_123")

    @patch("requests.post")
    def test_bad_request_response(self, mock_post, webex_provider):
        """Test handling of 400 bad request response."""
        # Setup mock response for bad request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="bad request"):
            webex_provider._notify(message="Test message", roomId="room_123")

    def test_missing_message_raises_error(self, webex_provider):
        """Test that sending without a message raises an error."""
        with pytest.raises(Exception, match="message is required"):
            webex_provider._notify(roomId="room_123")

    def test_missing_recipient_raises_error(self, webex_provider):
        """Test that sending without a recipient raises an error."""
        with pytest.raises(Exception, match="roomId, toPersonEmail, or toPersonId is required"):
            webex_provider._notify(message="Test message")

    def test_validate_config(self, webex_provider):
        """Test that configuration is validated correctly."""
        webex_provider.validate_config()
        assert webex_provider.authentication_config.access_token == "test_access_token_12345"

    @patch("requests.post")
    def test_validate_scopes_success(self, mock_post, webex_provider):
        """Test successful scope validation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "test_msg"}
        mock_post.return_value = mock_response

        result = webex_provider.validate_scopes()
        assert result == {"send_message": True}

    @patch("requests.post")
    def test_validate_scopes_failure(self, mock_post, webex_provider):
        """Test failed scope validation."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = webex_provider.validate_scopes()
        assert "send_message" in result
        assert result["send_message"] != True
