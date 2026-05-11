"""
Tests for WeCom Provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.wecom_provider.wecom_provider import WeComProvider
from keep.providers.models.provider_config import ProviderConfig


class TestWeComProvider:
    """Test cases for WeCom Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def wecom_config(self):
        """Create a test WeCom configuration."""
        return ProviderConfig(
            description="Test WeCom Provider",
            authentication={
                "webhook_key": "test_webhook_key_12345",
            },
        )

    @pytest.fixture
    def wecom_provider(self, context_manager, wecom_config):
        """Create a WeCom provider instance."""
        return WeComProvider(
            context_manager=context_manager,
            provider_id="test_wecom_provider",
            config=wecom_config,
        )

    @patch("requests.post")
    def test_send_text_message(self, mock_post, wecom_provider):
        """Test sending a plain text message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # Send message
        result = wecom_provider._notify(message="Test alert message")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify URL
        assert call_args[0][0] == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test_webhook_key_12345"

        # Verify headers
        assert call_args[1]["headers"]["Content-Type"] == "application/json"

        # Verify payload
        assert call_args[1]["json"]["msgtype"] == "text"
        assert call_args[1]["json"]["text"]["content"] == "Test alert message"

        # Verify return value
        assert result["message"] == "Test alert message"
        assert result["status"] == 0
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_markdown_message(self, mock_post, wecom_provider):
        """Test sending a markdown message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # Send markdown message
        result = wecom_provider._notify(
            message="**Bold** alert message",
            markdown=True,
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload
        assert call_args[1]["json"]["msgtype"] == "markdown"
        assert call_args[1]["json"]["markdown"]["content"] == "**Bold** alert message"

        # Verify return value
        assert result["message"] == "**Bold** alert message"

    @patch("requests.post")
    def test_send_message_with_mentions(self, mock_post, wecom_provider):
        """Test sending a message with @mentions."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # Send message with mentions
        result = wecom_provider._notify(
            message="Alert with mentions",
            mentioned_mobile_list=["13800000000", "13900000000"],
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload includes mentions
        assert call_args[1]["json"]["text"]["mentioned_mobile_list"] == ["13800000000", "13900000000"]

    @patch("requests.post")
    def test_api_error_response(self, mock_post, wecom_provider):
        """Test handling of WeCom API error response."""
        # Setup mock response with WeCom API error
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 40008, "errmsg": "invalid message type"}
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="failed to send message"):
            wecom_provider._notify(message="Test message")

    @patch("requests.post")
    def test_unauthorized_response(self, mock_post, wecom_provider):
        """Test handling of 401 unauthorized response."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Authentication failed"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="unauthorized - invalid webhook key"):
            wecom_provider._notify(message="Test message")

    @patch("requests.post")
    def test_bad_request_response(self, mock_post, wecom_provider):
        """Test handling of 400 bad request response."""
        # Setup mock response for bad request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="bad request"):
            wecom_provider._notify(message="Test message")

    def test_missing_message_raises_error(self, wecom_provider):
        """Test that sending without a message raises an error."""
        with pytest.raises(Exception, match="message is required"):
            wecom_provider._notify()

    def test_validate_config(self, wecom_provider):
        """Test that configuration is validated correctly."""
        wecom_provider.validate_config()
        assert wecom_provider.authentication_config.webhook_key == "test_webhook_key_12345"

    @patch("requests.post")
    def test_validate_scopes_success(self, mock_post, wecom_provider):
        """Test successful scope validation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        result = wecom_provider.validate_scopes()
        assert result == {"send_message": True}

    @patch("requests.post")
    def test_validate_scopes_failure(self, mock_post, wecom_provider):
        """Test failed scope validation."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = wecom_provider.validate_scopes()
        assert "send_message" in result
        assert result["send_message"] != True
