"""
Tests for Rocket.Chat Provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.rocketchat_provider.rocketchat_provider import RocketchatProvider
from keep.providers.models.provider_config import ProviderConfig


class TestRocketchatProvider:
    """Test cases for Rocket.Chat Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def rocketchat_config(self):
        """Create a test Rocket.Chat configuration."""
        return ProviderConfig(
            description="Test Rocket.Chat Provider",
            authentication={
                "access_token": "test_access_token_12345",
                "user_id": "test_user_id_67890",
            },
            payload={
                "base_url": "https://chat.example.com",
            },
        )

    @pytest.fixture
    def rocketchat_provider(self, context_manager, rocketchat_config):
        """Create a Rocket.Chat provider instance."""
        return RocketchatProvider(
            context_manager=context_manager,
            provider_id="test_rocketchat_provider",
            config=rocketchat_config,
        )

    @patch("requests.post")
    def test_send_text_message(self, mock_post, rocketchat_provider):
        """Test sending a plain text message to a channel."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "ts": 1234567890}
        mock_post.return_value = mock_response

        # Send message
        result = rocketchat_provider._notify(message="Test alert message", room="#general")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify URL
        assert call_args[0][0] == "https://chat.example.com/api/v1/chat.postMessage"

        # Verify headers
        assert call_args[1]["headers"]["X-Auth-Token"] == "test_access_token_12345"
        assert call_args[1]["headers"]["X-User-Id"] == "test_user_id_67890"

        # Verify payload
        assert call_args[1]["json"]["text"] == "Test alert message"
        assert call_args[1]["json"]["channel"] == "#general"

        # Verify return value
        assert result["message"] == "Test alert message"
        assert result["room"] == "#general"
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_message_to_dm(self, mock_post, rocketchat_provider):
        """Test sending a message to a direct message room."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "ts": 1234567890}
        mock_post.return_value = mock_response

        # Send message to user DM
        result = rocketchat_provider._notify(message="DM alert", room="@username")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload
        assert call_args[1]["json"]["text"] == "DM alert"
        assert call_args[1]["json"]["roomId"] == "@username"

    @patch("requests.post")
    def test_send_message_with_alias(self, mock_post, rocketchat_provider):
        """Test sending a message with a custom alias."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "ts": 1234567890}
        mock_post.return_value = mock_response

        # Send message with alias
        result = rocketchat_provider._notify(
            message="Alert with alias",
            room="#general",
            alias="Keep Bot",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload includes alias
        assert call_args[1]["json"]["text"] == "Alert with alias"
        assert call_args[1]["json"]["alias"] == "Keep Bot"

    @patch("requests.post")
    def test_send_message_with_emoji(self, mock_post, rocketchat_provider):
        """Test sending a message with a custom emoji avatar."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "ts": 1234567890}
        mock_post.return_value = mock_response

        # Send message with emoji
        result = rocketchat_provider._notify(
            message="Alert with emoji",
            room="#general",
            emoji=":warning:",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload includes emoji
        assert call_args[1]["json"]["emoji"] == ":warning:"

    @patch("requests.post")
    def test_unauthorized_response(self, mock_post, rocketchat_provider):
        """Test handling of 401 unauthorized response."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="unauthorized"):
            rocketchat_provider._notify(message="Test message", room="#general")

    @patch("requests.post")
    def test_bad_request_response(self, mock_post, rocketchat_provider):
        """Test handling of 400 bad request response."""
        # Setup mock response for bad request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid channel"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="bad request"):
            rocketchat_provider._notify(message="Test message", room="#general")

    def test_missing_message_raises_error(self, rocketchat_provider):
        """Test that sending without a message raises an error."""
        with pytest.raises(Exception, match="message is required"):
            rocketchat_provider._notify(room="#general")

    def test_missing_room_raises_error(self, rocketchat_provider):
        """Test that sending without a room raises an error."""
        with pytest.raises(Exception, match="room is required"):
            rocketchat_provider._notify(message="Test message")

    def test_validate_config(self, rocketchat_provider):
        """Test that configuration is validated correctly."""
        rocketchat_provider.validate_config()
        assert rocketchat_provider.authentication_config.access_token == "test_access_token_12345"
        assert rocketchat_provider.authentication_config.user_id == "test_user_id_67890"
        assert rocketchat_provider.payload_config.base_url == "https://chat.example.com"

    @patch("requests.post")
    def test_validate_scopes_success(self, mock_post, rocketchat_provider):
        """Test successful scope validation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "ts": 1234567890}
        mock_post.return_value = mock_response

        result = rocketchat_provider.validate_scopes()
        assert result == {"send_message": True}

    @patch("requests.post")
    def test_validate_scopes_failure(self, mock_post, rocketchat_provider):
        """Test failed scope validation."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = rocketchat_provider.validate_scopes()
        assert "send_message" in result
        assert result["send_message"] != True
