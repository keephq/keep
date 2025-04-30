from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.teams_provider.teams_provider import TeamsProvider


@pytest.fixture
def teams_provider():
    """Create a Teams provider instance for testing"""
    context_manager = ContextManager(
        tenant_id="test-tenant", workflow_id="test-workflow"
    )
    config = ProviderConfig(
        id="teams-test",
        description="Teams Output Provider",
        authentication={"webhook_url": "https://example.webhook.office.com/webhook"},
    )
    return TeamsProvider(context_manager, provider_id="teams-test", config=config)


@pytest.fixture
def mock_response():
    """Create a mock response for requests.post"""
    response = MagicMock()
    response.ok = True
    response.text = "Success"
    return response


@patch("requests.post")
def test_notify_with_mentions(mock_post, teams_provider, mock_response):
    """Test sending an Adaptive Card with a single user mention"""
    # Setup mock response
    mock_post.return_value = mock_response

    # Test with mentions
    result = teams_provider.notify(
        typeCard="message",
        sections=[
            {
                "type": "TextBlock",
                "text": "Hello <at>John Doe</at>, please review this alert!",
            }
        ],
        mentions=[{"id": "john.doe@example.com", "name": "John Doe"}],
    )

    # Verify the response
    assert result == {"response_text": "Success"}

    # Verify the request payload
    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]

    # Check that the payload has the correct structure
    assert payload["type"] == "message"
    assert len(payload["attachments"]) == 1

    # Check the attachment content
    attachment = payload["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert attachment["contentUrl"] is None

    # Check the card content
    card_content = attachment["content"]
    assert card_content["type"] == "AdaptiveCard"
    assert card_content["version"] == "1.2"

    # Check the body
    assert len(card_content["body"]) == 1
    assert card_content["body"][0]["type"] == "TextBlock"
    assert (
        card_content["body"][0]["text"]
        == "Hello <at>John Doe</at>, please review this alert!"
    )

    # Check the mentions
    assert "msteams" in card_content
    assert "entities" in card_content["msteams"]
    assert len(card_content["msteams"]["entities"]) == 1

    entity = card_content["msteams"]["entities"][0]
    assert entity["type"] == "mention"
    assert entity["text"] == "<at>John Doe</at>"
    assert entity["mentioned"]["id"] == "john.doe@example.com"
    assert entity["mentioned"]["name"] == "John Doe"


@patch("requests.post")
def test_notify_with_multiple_mentions(mock_post, teams_provider, mock_response):
    """Test sending an Adaptive Card with multiple user mentions"""
    # Setup mock response
    mock_post.return_value = mock_response

    # Test with multiple mentions
    result = teams_provider.notify(
        typeCard="message",
        sections=[
            {
                "type": "TextBlock",
                "text": "Hello <at>John Doe</at> and <at>Jane Smith</at>, please review this alert!",
            }
        ],
        mentions=[
            {"id": "john.doe@example.com", "name": "John Doe"},
            {"id": "49c4641c-ab91-4248-aebb-6a7de286397b", "name": "Jane Smith"},
        ],
    )

    # Verify the response
    assert result == {"response_text": "Success"}

    # Verify the request payload
    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]

    # Check the mentions
    card_content = payload["attachments"][0]["content"]
    assert "msteams" in card_content
    assert "entities" in card_content["msteams"]
    assert len(card_content["msteams"]["entities"]) == 2

    # Check first mention
    entity1 = card_content["msteams"]["entities"][0]
    assert entity1["type"] == "mention"
    assert entity1["text"] == "<at>John Doe</at>"
    assert entity1["mentioned"]["id"] == "john.doe@example.com"
    assert entity1["mentioned"]["name"] == "John Doe"

    # Check second mention
    entity2 = card_content["msteams"]["entities"][1]
    assert entity2["type"] == "mention"
    assert entity2["text"] == "<at>Jane Smith</at>"
    assert entity2["mentioned"]["id"] == "49c4641c-ab91-4248-aebb-6a7de286397b"
    assert entity2["mentioned"]["name"] == "Jane Smith"


@patch("requests.post")
def test_notify_with_invalid_mention_format(mock_post, teams_provider, mock_response):
    """Test sending an Adaptive Card with invalid mention format"""
    # Setup mock response
    mock_post.return_value = mock_response

    # Test with invalid mention format
    result = teams_provider.notify(
        typeCard="message",
        sections=[
            {
                "type": "TextBlock",
                "text": "Hello <at>John Doe</at>, please review this alert!",
            }
        ],
        mentions=[{"name": "John Doe"}],  # Missing 'id' field
    )

    # Verify the response
    assert result == {"response_text": "Success"}

    # Verify the request payload
    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]

    # Check that no mentions were added due to invalid format
    card_content = payload["attachments"][0]["content"]
    assert "msteams" not in card_content


@patch("requests.post")
def test_notify_with_string_mentions(mock_post, teams_provider, mock_response):
    """Test sending an Adaptive Card with mentions provided as a JSON string"""
    # Setup mock response
    mock_post.return_value = mock_response

    # Test with mentions as JSON string
    result = teams_provider.notify(
        typeCard="message",
        sections=[
            {
                "type": "TextBlock",
                "text": "Hello <at>John Doe</at>, please review this alert!",
            }
        ],
        mentions='[{"id": "john.doe@example.com", "name": "John Doe"}]',
    )

    # Verify the response
    assert result == {"response_text": "Success"}

    # Verify the request payload
    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]

    # Check the mentions
    card_content = payload["attachments"][0]["content"]
    assert "msteams" in card_content
    assert "entities" in card_content["msteams"]
    assert len(card_content["msteams"]["entities"]) == 1

    entity = card_content["msteams"]["entities"][0]
    assert entity["type"] == "mention"
    assert entity["text"] == "<at>John Doe</at>"
    assert entity["mentioned"]["id"] == "john.doe@example.com"
    assert entity["mentioned"]["name"] == "John Doe"
