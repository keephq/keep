"""
Tests for LINE Notify Provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.line_notify_provider.line_notify_provider import LineNotifyProvider
from keep.providers.models.provider_config import ProviderConfig


class TestLineNotifyProvider:
    """Test cases for LINE Notify Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def line_notify_config(self):
        """Create a test LINE Notify configuration."""
        return ProviderConfig(
            description="Test LINE Notify Provider",
            authentication={
                "access_token": "test_access_token_12345",
            },
        )

    @pytest.fixture
    def line_notify_provider(self, context_manager, line_notify_config):
        """Create a LINE Notify provider instance."""
        return LineNotifyProvider(
            context_manager=context_manager,
            provider_id="test_line_notify_provider",
            config=line_notify_config,
        )

    @patch("requests.post")
    def test_send_text_message(self, mock_post, line_notify_provider):
        """Test sending a plain text message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": 200, "message": "ok"}
        mock_post.return_value = mock_response

        # Send message
        result = line_notify_provider._notify(message="Test alert message")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Verify URL
        assert call_args[0][0] == "https://notify-api.line.me/api/notify"
        
        # Verify headers
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_access_token_12345"
        
        # Verify payload
        assert call_args[1]["data"]["message"] == "Test alert message"
        
        # Verify return value
        assert result["message"] == "Test alert message"
        assert result["status"] == 200
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_message_with_image(self, mock_post, line_notify_provider):
        """Test sending a message with image URLs."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": 200, "message": "ok"}
        mock_post.return_value = mock_response

        # Send message with image
        result = line_notify_provider._notify(
            message="Alert with image",
            image_thumbnail="https://example.com/thumb.png",
            image_fullsize="https://example.com/full.png",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Verify payload includes image URLs
        assert call_args[1]["data"]["message"] == "Alert with image"
        assert call_args[1]["data"]["imageThumbnail"] == "https://example.com/thumb.png"
        assert call_args[1]["data"]["imageFullsize"] == "https://example.com/full.png"
        
        # Verify return value
        assert result["message"] == "Alert with image"

    @patch("requests.post")
    def test_send_message_with_sticker(self, mock_post, line_notify_provider):
        """Test sending a message with a sticker."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": 200, "message": "ok"}
        mock_post.return_value = mock_response

        # Send message with sticker
        result = line_notify_provider._notify(
            message="Alert with sticker",
            sticker_package_id="446",
            sticker_id="1988",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Verify payload includes sticker info
        assert call_args[1]["data"]["stickerPackageId"] == "446"
        assert call_args[1]["data"]["stickerId"] == "1988"

    @patch("requests.post")
    def test_send_silent_notification(self, mock_post, line_notify_provider):
        """Test sending a silent notification."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": 200, "message": "ok"}
        mock_post.return_value = mock_response

        # Send silent message
        result = line_notify_provider._notify(
            message="Silent alert",
            notification_disabled=True,
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Verify notification disabled flag
        assert call_args[1]["data"]["notificationDisabled"] == "true"

    @patch("requests.post")
    def test_unauthorized_response(self, mock_post, line_notify_provider):
        """Test handling of 401 unauthorized response."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Authentication failed"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="unauthorized - invalid access token"):
            line_notify_provider._notify(message="Test message")

    @patch("requests.post")
    def test_bad_request_response(self, mock_post, line_notify_provider):
        """Test handling of 400 bad request response."""
        # Setup mock response for bad request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Message is too long"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="bad request"):
            line_notify_provider._notify(message="Test message")

    def test_missing_message_raises_error(self, line_notify_provider):
        """Test that sending without a message raises an error."""
        with pytest.raises(Exception, match="message is required"):
            line_notify_provider._notify()

    def test_validate_config(self, line_notify_provider):
        """Test that configuration is validated correctly."""
        line_notify_provider.validate_config()
        assert line_notify_provider.authentication_config.access_token == "test_access_token_12345"

    @patch("requests.post")
    def test_validate_scopes_success(self, mock_post, line_notify_provider):
        """Test successful scope validation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": 200, "message": "ok"}
        mock_post.return_value = mock_response

        result = line_notify_provider.validate_scopes()
        assert result == {"send_message": True}

    @patch("requests.post")
    def test_validate_scopes_failure(self, mock_post, line_notify_provider):
        """Test failed scope validation."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = line_notify_provider.validate_scopes()
        assert "send_message" in result
        assert result["send_message"] != True
