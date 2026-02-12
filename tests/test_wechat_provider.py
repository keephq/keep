from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.wechat_provider.wechat_provider import WechatProvider


@pytest.fixture
def wechat_provider():
    """Create a WeChat provider instance for testing"""
    context_manager = ContextManager(
        tenant_id="test-tenant", workflow_id="test-workflow"
    )
    config = ProviderConfig(
        id="wechat-test",
        description="WeChat Work Output Provider",
        authentication={"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key"},
    )
    return WechatProvider(context_manager, provider_id="wechat-test", config=config)


@pytest.fixture
def mock_response():
    """Create a mock response for requests.post"""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"errcode": 0, "errmsg": "ok"}
    return response


@patch("requests.post")
def test_notify_text_message(mock_post, wechat_provider, mock_response):
    """Test sending a simple text message"""
    # Setup mock response
    mock_post.return_value = mock_response

    # Test simple text message
    result = wechat_provider._notify(content="Test alert from Keep!")
    
    # Verify the request was made
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    
    # Check the payload
    assert kwargs["json"]["msgtype"] == "text"
    assert kwargs["json"]["text"]["content"] == "Test alert from Keep!"


@patch("requests.post")
def test_notify_markdown_message(mock_post, wechat_provider, mock_response):
    """Test sending a markdown message"""
    # Setup mock response
    mock_post.return_value = mock_response

    # Test markdown message
    result = wechat_provider._notify(
        msg_type="markdown",
        markdown_content="**Alert**: Service is down!\n> Time: 2024-01-01 12:00:00"
    )
    
    # Verify the request was made
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    
    # Check the payload
    assert kwargs["json"]["msgtype"] == "markdown"
    assert kwargs["json"]["markdown"]["content"] == "**Alert**: Service is down!\n> Time: 2024-01-01 12:00:00"


@patch("requests.post")
def test_notify_with_mentions(mock_post, wechat_provider, mock_response):
    """Test sending a message with @all mention"""
    # Setup mock response
    mock_post.return_value = mock_response

    # Test with mentions
    result = wechat_provider._notify(
        content="Critical alert!",
        mentioned_list=["@all"]
    )
    
    # Verify the request was made
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    
    # Check the payload
    assert kwargs["json"]["msgtype"] == "text"
    assert kwargs["json"]["text"]["mentioned_list"] == ["@all"]


@patch("requests.post")
def test_notify_with_mobile_mentions(mock_post, wechat_provider, mock_response):
    """Test sending a message with mobile number mentions"""
    # Setup mock response
    mock_post.return_value = mock_response

    # Test with mobile mentions
    result = wechat_provider._notify(
        content="Please check this alert!",
        mentioned_mobile_list=["+8613800138000", "+8613900139000"]
    )
    
    # Verify the request was made
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    
    # Check the payload
    assert kwargs["json"]["msgtype"] == "text"
    assert kwargs["json"]["text"]["mentioned_mobile_list"] == ["+8613800138000", "+8613900139000"]


def test_validate_config():
    """Test configuration validation"""
    context_manager = ContextManager(tenant_id="test-tenant")
    
    # Valid config
    config = ProviderConfig(
        authentication={"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test"}
    )
    provider = WechatProvider(context_manager, "wechat-test", config)
    provider.validate_config()  # Should not raise


def test_provider_properties():
    """Test provider metadata"""
    context_manager = ContextManager(tenant_id="test-tenant")
    config = ProviderConfig(authentication={"webhook_url": "https://test.com"})
    provider = WechatProvider(context_manager, "wechat-test", config)
    
    assert provider.PROVIDER_DISPLAY_NAME == "WeChat Work"
    assert "Collaboration" in provider.PROVIDER_CATEGORY
