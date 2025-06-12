"""
Tests for SMTP Provider with HTML email support
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.smtp_provider.smtp_provider import SmtpProvider
from keep.providers.models.provider_config import ProviderConfig


class TestSmtpProvider:
    """Test cases for SMTP Provider with HTML support."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def smtp_config(self):
        """Create a test SMTP configuration."""
        return ProviderConfig(
            description="Test SMTP Provider",
            authentication={
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "encryption": "TLS",
                "smtp_username": "test@example.com",
                "smtp_password": "testpassword",
            },
        )

    @pytest.fixture
    def smtp_provider(self, context_manager, smtp_config):
        """Create an SMTP provider instance."""
        return SmtpProvider(
            context_manager=context_manager,
            provider_id="test_smtp_provider",
            config=smtp_config,
        )

    @patch("keep.providers.smtp_provider.smtp_provider.SMTP")
    def test_send_plain_text_email(self, mock_smtp_class, smtp_provider):
        """Test sending a plain text email."""
        # Setup mock SMTP instance
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # Send plain text email
        result = smtp_provider._notify(
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@example.com",
            subject="Test Subject",
            body="This is a plain text email",
        )

        # Verify SMTP was called correctly
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587)
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@example.com", "testpassword")
        
        # Verify email was sent
        mock_smtp.sendmail.assert_called_once()
        call_args = mock_smtp.sendmail.call_args
        assert call_args[0][0] == "sender@example.com"
        assert call_args[0][1] == "recipient@example.com"
        
        # Verify the email content contains plain text
        email_content = call_args[0][2]
        assert "Content-Type: text/plain" in email_content
        assert "This is a plain text email" in email_content
        
        # Verify return value
        assert result == {
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": "Test Subject",
            "body": "This is a plain text email",
        }

    @patch("keep.providers.smtp_provider.smtp_provider.SMTP")
    def test_send_html_email(self, mock_smtp_class, smtp_provider):
        """Test sending an HTML email."""
        # Setup mock SMTP instance
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # Send HTML email
        result = smtp_provider._notify(
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@example.com",
            subject="Test HTML Subject",
            html="<p>This is an <strong>HTML</strong> email</p>",
        )

        # Verify SMTP was called correctly
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587)
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@example.com", "testpassword")
        
        # Verify email was sent
        mock_smtp.sendmail.assert_called_once()
        call_args = mock_smtp.sendmail.call_args
        assert call_args[0][0] == "sender@example.com"
        assert call_args[0][1] == "recipient@example.com"
        
        # Verify the email content contains HTML
        email_content = call_args[0][2]
        assert "Content-Type: text/html" in email_content
        assert "<p>This is an <strong>HTML</strong> email</p>" in email_content
        
        # Verify return value
        assert result == {
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": "Test HTML Subject",
            "html": "<p>This is an <strong>HTML</strong> email</p>",
        }

    @patch("keep.providers.smtp_provider.smtp_provider.SMTP")
    def test_send_html_email_with_both_body_and_html(self, mock_smtp_class, smtp_provider):
        """Test that HTML takes precedence when both body and html are provided."""
        # Setup mock SMTP instance
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # Send email with both body and html
        result = smtp_provider._notify(
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@example.com",
            subject="Test Subject",
            body="Plain text content",
            html="<p>HTML content</p>",
        )

        # Verify email was sent
        mock_smtp.sendmail.assert_called_once()
        call_args = mock_smtp.sendmail.call_args
        
        # Verify HTML content is used (not plain text)
        email_content = call_args[0][2]
        assert "Content-Type: text/html" in email_content
        assert "<p>HTML content</p>" in email_content
        assert "Content-Type: text/plain" not in email_content
        
        # Verify return value contains both
        assert result == {
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": "Test Subject",
            "body": "Plain text content",
            "html": "<p>HTML content</p>",
        }

    @patch("keep.providers.smtp_provider.smtp_provider.SMTP")
    def test_send_email_to_multiple_recipients(self, mock_smtp_class, smtp_provider):
        """Test sending an email to multiple recipients."""
        # Setup mock SMTP instance
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        recipients = ["recipient1@example.com", "recipient2@example.com"]
        
        # Send HTML email to multiple recipients
        result = smtp_provider._notify(
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email=recipients,
            subject="Test Multi-recipient",
            html="<p>Email to multiple recipients</p>",
        )

        # Verify email was sent
        mock_smtp.sendmail.assert_called_once()
        call_args = mock_smtp.sendmail.call_args
        assert call_args[0][0] == "sender@example.com"
        assert call_args[0][1] == recipients
        
        # Verify the To header contains all recipients
        email_content = call_args[0][2]
        assert "To: recipient1@example.com, recipient2@example.com" in email_content
        
        # Verify return value
        assert result == {
            "from": "sender@example.com",
            "to": recipients,
            "subject": "Test Multi-recipient",
            "html": "<p>Email to multiple recipients</p>",
        }

    @patch("keep.providers.smtp_provider.smtp_provider.SMTP")
    def test_send_email_without_body_or_html_raises_error(self, mock_smtp_class, smtp_provider):
        """Test that sending an email without body or html raises an error."""
        # Setup mock SMTP instance
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # Attempt to send email without body or html
        with pytest.raises(ValueError, match="Either 'body' or 'html' must be provided"):
            smtp_provider._notify(
                from_email="sender@example.com",
                from_name="Test Sender",
                to_email="recipient@example.com",
                subject="Test Subject",
            )

    @patch("keep.providers.smtp_provider.smtp_provider.SMTP_SSL")
    def test_ssl_encryption(self, mock_smtp_ssl_class, context_manager):
        """Test SMTP with SSL encryption."""
        # Create provider with SSL config
        ssl_config = ProviderConfig(
            description="Test SMTP Provider",
            authentication={
                "smtp_server": "smtp.example.com",
                "smtp_port": 465,
                "encryption": "SSL",
                "smtp_username": "test@example.com",
                "smtp_password": "testpassword",
            },
        )
        smtp_provider = SmtpProvider(
            context_manager=context_manager,
            provider_id="test_smtp_provider",
            config=ssl_config,
        )

        # Setup mock SMTP_SSL instance
        mock_smtp = MagicMock()
        mock_smtp_ssl_class.return_value = mock_smtp

        # Send email
        smtp_provider._notify(
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@example.com",
            subject="Test SSL",
            html="<p>SSL test</p>",
        )

        # Verify SMTP_SSL was used
        mock_smtp_ssl_class.assert_called_once_with("smtp.example.com", 465)
        mock_smtp.login.assert_called_once_with("test@example.com", "testpassword")
        mock_smtp.sendmail.assert_called_once()

    @patch("keep.providers.smtp_provider.smtp_provider.SMTP")
    def test_no_encryption(self, mock_smtp_class, context_manager):
        """Test SMTP without encryption."""
        # Create provider with no encryption config
        no_enc_config = ProviderConfig(
            description="Test SMTP Provider",
            authentication={
                "smtp_server": "smtp.example.com",
                "smtp_port": 25,
                "encryption": "None",
                "smtp_username": "",
                "smtp_password": "",
            },
        )
        smtp_provider = SmtpProvider(
            context_manager=context_manager,
            provider_id="test_smtp_provider",
            config=no_enc_config,
        )

        # Setup mock SMTP instance
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # Send email
        smtp_provider._notify(
            from_email="sender@example.com",
            from_name="Test Sender",
            to_email="recipient@example.com",
            subject="Test No Encryption",
            body="No encryption test",
        )

        # Verify SMTP was used without TLS
        mock_smtp_class.assert_called_once_with("smtp.example.com", 25)
        mock_smtp.starttls.assert_not_called()
        mock_smtp.login.assert_not_called()  # No credentials provided
        mock_smtp.sendmail.assert_called_once()

    @patch("keep.providers.smtp_provider.smtp_provider.SMTP")
    def test_empty_from_name(self, mock_smtp_class, smtp_provider):
        """Test sending email with empty from_name."""
        # Setup mock SMTP instance
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # Send email with empty from_name
        smtp_provider._notify(
            from_email="sender@example.com",
            from_name="",
            to_email="recipient@example.com",
            subject="Test Subject",
            html="<p>Test</p>",
        )

        # Verify email was sent
        mock_smtp.sendmail.assert_called_once()
        call_args = mock_smtp.sendmail.call_args
        
        # Verify the From header contains only email
        email_content = call_args[0][2]
        assert "From: sender@example.com" in email_content
        assert "Test Sender" not in email_content

    def test_validate_scopes_success(self, smtp_provider):
        """Test successful scope validation."""
        with patch.object(smtp_provider, "generate_smtp_client") as mock_generate:
            mock_smtp = MagicMock()
            mock_generate.return_value = mock_smtp
            
            result = smtp_provider.validate_scopes()
            
            assert result == {"send_email": True}
            mock_smtp.quit.assert_called_once()

    def test_validate_scopes_failure(self, smtp_provider):
        """Test failed scope validation."""
        with patch.object(smtp_provider, "generate_smtp_client") as mock_generate:
            mock_generate.side_effect = Exception("Connection failed")
            
            result = smtp_provider.validate_scopes()
            
            assert result == {"send_email": "Connection failed"}