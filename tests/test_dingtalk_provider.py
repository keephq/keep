"""
Tests for DingTalk Provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.dingtalk_provider.dingtalk_provider import DingTalkProvider
from keep.providers.models.provider_config import ProviderConfig


class TestDingTalkProvider:
    """Test cases for DingTalk Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def dingtalk_config(self):
        """Create a test DingTalk configuration."""
        return ProviderConfig(
            description="Test DingTalk Provider",
            authentication={
                "access_token": "test_access_token_12345",
            },
        )

    @pytest.fixture
    def dingtalk_config_with_secret(self):
        """Create a test DingTalk configuration with secret."""
        return ProviderConfig(
            description="Test DingTalk Provider with Secret",
            authentication={
                "access_token": "test_access_token_12345",
                "secret": "test_secret_67890",
            },
        )

    @pytest.fixture
    def dingtalk_provider(self, context_manager, dingtalk_config):
        """Create a DingTalk provider instance."""
        return DingTalkProvider(
            context_manager=context_manager,
            provider_id="test_dingtalk_provider",
            config=dingtalk_config,
        )

    @pytest.fixture
    def dingtalk_provider_with_secret(self, context_manager, dingtalk_config_with_secret):
        """Create a DingTalk provider instance with secret."""
        return DingTalkProvider(
            context_manager=context_manager,
            provider_id="test_dingtalk_provider_secret",
            config=dingtalk_config_with_secret,
        )

    @patch("requests.post")
    def test_send_text_message(self, mock_post, dingtalk_provider):
        """Test sending a plain text message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # Send message
        result = dingtalk_provider._notify(message="Test alert message")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify URL
        assert call_args[0][0] == "https://oapi.dingtalk.com/robot/send"

        # Verify params
        assert call_args[1]["params"]["access_token"] == "test_access_token_12345"
        assert "timestamp" not in call_args[1]["params"]
        assert "sign" not in call_args[1]["params"]

        # Verify payload
        assert call_args[1]["json"]["msgtype"] == "text"
        assert call_args[1]["json"]["text"]["content"] == "Test alert message"

        # Verify return value
        assert result["message"] == "Test alert message"
        assert result["errcode"] == 0
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_text_message_with_secret(self, mock_post, dingtalk_provider_with_secret):
        """Test sending a text message with signature verification."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # Send message
        result = dingtalk_provider_with_secret._notify(message="Test alert with secret")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify params include signature
        assert call_args[1]["params"]["access_token"] == "test_access_token_12345"
        assert "timestamp" in call_args[1]["params"]
        assert "sign" in call_args[1]["params"]

        # Verify return value
        assert result["message"] == "Test alert with secret"
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_markdown_message(self, mock_post, dingtalk_provider):
        """Test sending a markdown message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # Send markdown message
        result = dingtalk_provider._notify(
            message="### Alert\nServer is down",
            title="Critical Alert",
            msgtype="markdown",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload
        assert call_args[1]["json"]["msgtype"] == "markdown"
        assert call_args[1]["json"]["markdown"]["title"] == "Critical Alert"
        assert call_args[1]["json"]["markdown"]["text"] == "### Alert\nServer is down"

    @patch("requests.post")
    def test_send_message_with_at_mobiles(self, mock_post, dingtalk_provider):
        """Test sending a message with @mentions by mobile."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # Send message with @mentions
        result = dingtalk_provider._notify(
            message="Alert: check this",
            at_mobiles=["18200000000", "18300000000"],
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify at info
        assert call_args[1]["json"]["at"]["atMobiles"] == ["18200000000", "18300000000"]

    @patch("requests.post")
    def test_send_message_with_at_all(self, mock_post, dingtalk_provider):
        """Test sending a message with @all."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # Send message with @all
        result = dingtalk_provider._notify(
            message="Emergency alert",
            is_at_all=True,
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify at info
        assert call_args[1]["json"]["at"]["isAtAll"] is True

    @patch("requests.post")
    def test_api_error_response(self, mock_post, dingtalk_provider):
        """Test handling of API error response (errcode != 0)."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 310000, "errmsg": "keywords not in content"}
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="API error"):
            dingtalk_provider._notify(message="Test message")

    @patch("requests.post")
    def test_unauthorized_response(self, mock_post, dingtalk_provider):
        """Test handling of 401 unauthorized response."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Authentication failed"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="unauthorized - invalid access token"):
            dingtalk_provider._notify(message="Test message")

    @patch("requests.post")
    def test_bad_request_response(self, mock_post, dingtalk_provider):
        """Test handling of 400 bad request response."""
        # Setup mock response for bad request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="bad request"):
            dingtalk_provider._notify(message="Test message")

    def test_missing_message_raises_error(self, dingtalk_provider):
        """Test that sending without a message raises an error."""
        with pytest.raises(Exception, match="message is required"):
            dingtalk_provider._notify()

    def test_invalid_msgtype_raises_error(self, dingtalk_provider):
        """Test that invalid msgtype raises an error."""
        with pytest.raises(Exception, match="msgtype must be"):
            dingtalk_provider._send_message(message="Test", msgtype="invalid")

    def test_validate_config(self, dingtalk_provider):
        """Test that configuration is validated correctly."""
        dingtalk_provider.validate_config()
        assert dingtalk_provider.authentication_config.access_token == "test_access_token_12345"
        assert dingtalk_provider.authentication_config.secret is None

    def test_validate_config_with_secret(self, dingtalk_provider_with_secret):
        """Test that configuration with secret is validated correctly."""
        dingtalk_provider_with_secret.validate_config()
        assert dingtalk_provider_with_secret.authentication_config.access_token == "test_access_token_12345"
        assert dingtalk_provider_with_secret.authentication_config.secret == "test_secret_67890"

    @patch("requests.post")
    def test_validate_scopes_success(self, mock_post, dingtalk_provider):
        """Test successful scope validation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        result = dingtalk_provider.validate_scopes()
        assert result == {"send_message": True}

    @patch("requests.post")
    def test_validate_scopes_failure(self, mock_post, dingtalk_provider):
        """Test failed scope validation."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = dingtalk_provider.validate_scopes()
        assert "send_message" in result
        assert result["send_message"] != True

    def test_generate_sign(self, dingtalk_provider_with_secret):
        """Test signature generation."""
        timestamp, sign = dingtalk_provider_with_secret._generate_sign("test_secret")
        assert timestamp is not None
        assert sign is not None
        assert len(sign) > 0
