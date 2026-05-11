"""
Tests for Matrix Provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.matrix_provider.matrix_provider import MatrixProvider
from keep.providers.models.provider_config import ProviderConfig


class TestMatrixProvider:
    """Test cases for Matrix Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def matrix_config(self):
        """Create a test Matrix configuration."""
        return ProviderConfig(
            description="Test Matrix Provider",
            authentication={
                "access_token": "test_access_token_12345",
                "homeserver_url": "https://matrix.org",
                "room_id": "!testroom:matrix.org",
            },
        )

    @pytest.fixture
    def matrix_provider(self, context_manager, matrix_config):
        """Create a Matrix provider instance."""
        return MatrixProvider(
            context_manager=context_manager,
            provider_id="test_matrix_provider",
            config=matrix_config,
        )

    @patch("requests.post")
    def test_send_text_message(self, mock_post, matrix_provider):
        """Test sending a plain text message."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"event_id": "$test1234567890"}
        mock_post.return_value = mock_response

        # Send message
        result = matrix_provider._notify(message="Test alert message")

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Verify URL
        assert call_args[0][0] == "https://matrix.org/_matrix/client/r0/rooms/!testroom:matrix.org/send/m.room.message"
        
        # Verify headers
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_access_token_12345"
        
        # Verify payload
        assert call_args[1]["json"]["body"] == "Test alert message"
        assert call_args[1]["json"]["msgtype"] == "m.text"
        
        # Verify return value
        assert result["message"] == "Test alert message"
        assert result["event_id"] == "$test1234567890"
        assert result["sent"] is True

    @patch("requests.post")
    def test_send_formatted_message(self, mock_post, matrix_provider):
        """Test sending a message with HTML formatting."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"event_id": "$test1234567890"}
        mock_post.return_value = mock_response

        # Send message with HTML formatting
        result = matrix_provider._notify(
            message="Alert with formatting",
            formatted_message="<b>Alert</b> with <i>formatting</i>",
        )

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Verify payload includes formatted message
        assert call_args[1]["json"]["body"] == "Alert with formatting"
        assert call_args[1]["json"]["formatted_body"] == "<b>Alert</b> with <i>formatting</i>"
        assert call_args[1]["json"]["format"] == "org.matrix.custom.html"
        
        # Verify return value
        assert result["message"] == "Alert with formatting"

    @patch("requests.post")
    def test_unauthorized_response(self, mock_post, matrix_provider):
        """Test handling of 401 unauthorized response."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Authentication failed"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="unauthorized - invalid access token"):
            matrix_provider._notify(message="Test message")

    @patch("requests.post")
    def test_bad_request_response(self, mock_post, matrix_provider):
        """Test handling of 400 bad request response."""
        # Setup mock response for bad request
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid room ID"
        mock_post.return_value = mock_response

        # Attempt to send message
        with pytest.raises(Exception, match="bad request"):
            matrix_provider._notify(message="Test message")

    def test_missing_message_raises_error(self, matrix_provider):
        """Test that sending without a message raises an error."""
        with pytest.raises(Exception, match="message is required"):
            matrix_provider._notify()

    def test_validate_config(self, matrix_provider):
        """Test that configuration is validated correctly."""
        matrix_provider.validate_config()
        assert matrix_provider.authentication_config.access_token == "test_access_token_12345"
        assert matrix_provider.authentication_config.homeserver_url == "https://matrix.org"
        assert matrix_provider.authentication_config.room_id == "!testroom:matrix.org"

    @patch("requests.post")
    def test_validate_scopes_success(self, mock_post, matrix_provider):
        """Test successful scope validation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"event_id": "$test1234567890"}
        mock_post.return_value = mock_response

        result = matrix_provider.validate_scopes()
        assert result == {"send_message": True}

    @patch("requests.post")
    def test_validate_scopes_failure(self, mock_post, matrix_provider):
        """Test failed scope validation."""
        # Setup mock response for unauthorized
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = matrix_provider.validate_scopes()
        assert "send_message" in result
        assert result["send_message"] != True

    def test_homeserver_url_stripped(self, context_manager):
        """Test that trailing slashes are stripped from homeserver URL."""
        config = ProviderConfig(
            description="Test Matrix Provider with trailing slash",
            authentication={
                "access_token": "test_token",
                "homeserver_url": "https://matrix.org/",
                "room_id": "!room:matrix.org",
            },
        )
        provider = MatrixProvider(
            context_manager=context_manager,
            provider_id="test_matrix_trailing",
            config=config,
        )
        provider.validate_config()
        assert provider.authentication_config.homeserver_url == "https://matrix.org/"

    @patch("requests.post")
    def test_homeserver_url_stripped_in_request(self, mock_post, context_manager):
        """Test that trailing slashes are stripped when building the request URL."""
        config = ProviderConfig(
            description="Test Matrix Provider with trailing slash",
            authentication={
                "access_token": "test_token",
                "homeserver_url": "https://matrix.org/",
                "room_id": "!room:matrix.org",
            },
        )
        provider = MatrixProvider(
            context_manager=context_manager,
            provider_id="test_matrix_trailing",
            config=config,
        )
        provider.validate_config()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"event_id": "$test1234567890"}
        mock_post.return_value = mock_response

        provider._notify(message="Test")

        call_args = mock_post.call_args
        assert call_args[0][0] == "https://matrix.org/_matrix/client/r0/rooms/!room:matrix.org/send/m.room.message"