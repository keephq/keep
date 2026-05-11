"""
Tests for Feishu Provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.feishu_provider.feishu_provider import FeishuProvider
from keep.providers.models.provider_config import ProviderConfig


class TestFeishuProvider:
    """Test cases for Feishu Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def feishu_config(self):
        """Create a test Feishu configuration."""
        return ProviderConfig(
            description="Test Feishu Provider",
            authentication={
                "webhook_token": "test_webhook_token_12345",
            },
        )

    @pytest.fixture
    def feishu_provider(self, context_manager, feishu_config):
        """Create a Feishu provider instance."""
        return FeishuProvider(
            context_manager=context_manager,
            provider_id="test_feishu_provider",
            config=feishu_config,
        )

    @patch("requests.post")
    def test_send_text_message(self, mock_post, feishu_provider):
        """Test sending a plain text message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "msg": "ok", "data": {}}
        mock_post.return_value = mock_response

        # Send message
        result = feishu_provider._notify(message="Test alert message")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify URL
        assert call_args[0][0] == "https://open.feishu.cn/open-apis/bot/v2/hook/test_webhook_token_12345"

        # Verify headers
        assert call_args[1]["headers"]["Content-Type"] == "application/json"

        # Verify payload
        assert call_args[1]["json"]["msg_type"] == "text"
        assert call_args[1]["json"]["content"]["text"] == "Test alert message"

        # Verify return value
        assert result["message"] == "Test alert message"
        assert result["status"] == "ok"
        assert result["sent"] is True

    @patch("requests.post")
    def test_api_error_response(self, mock_post, feishu_provider):
        """Test handling of API error response (HTTP 200 but non-zero code)."""
        # Setup mock response for API error
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 9499, "msg": "Bad Request"}
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="Bad Request"):
            feishu_provider._notify(message="Test message")

    @patch("requests.post")
    def test_bad_request_response(self, mock_post, feishu_provider):
        """Test handling of 400 bad request response."""
        # Setup mock response for bad request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="bad request"):
            feishu_provider._notify(message="Test message")

    @patch("requests.post")
    def test_server_error_response(self, mock_post, feishu_provider):
        """Test handling of 500 server error response."""
        # Setup mock response for server error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="failed to send message"):
            feishu_provider._notify(message="Test message")

    def test_missing_message_raises_error(self, feishu_provider):
        """Test that sending without a message raises an error."""
        with pytest.raises(Exception, match="message is required"):
            feishu_provider._notify()

    def test_validate_config(self, feishu_provider):
        """Test that configuration is validated correctly."""
        feishu_provider.validate_config()
        assert feishu_provider.authentication_config.webhook_token == "test_webhook_token_12345"

    @patch("requests.post")
    def test_validate_scopes_success(self, mock_post, feishu_provider):
        """Test successful scope validation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "msg": "ok", "data": {}}
        mock_post.return_value = mock_response

        result = feishu_provider.validate_scopes()
        assert result == {"send_message": True}

    @patch("requests.post")
    def test_validate_scopes_failure(self, mock_post, feishu_provider):
        """Test failed scope validation."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        result = feishu_provider.validate_scopes()
        assert "send_message" in result
        assert result["send_message"] != True
