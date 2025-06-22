from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.teams_provider.teams_provider import TeamsProvider
from keep.api.models.alert import AlertDto, AlertStatus, AlertSeverity
from keep.iohandler.iohandler import IOHandler, RenderException


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
    response.status_code = 200
    response.ok = True
    response.text = "Success"
    response.json.return_value = {"status": "success"}
    return response


@pytest.fixture
def alert_with_namespace():
    """Create an alert with namespace for testing"""
    return AlertDto(
        id="test-alert-1",
        name="Test Alert with Namespace",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived="2024-01-01T00:00:00Z",
        source=["prometheusSvam"],
        labels={"namespace": "production"},
        description="Test alert with namespace field"
    )


@pytest.fixture  
def alert_without_namespace():
    """Create an alert without namespace for testing"""
    return AlertDto(
        id="test-alert-2", 
        name="Test Alert without Namespace",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived="2024-01-01T00:00:00Z",
        source=["prometheusSvam"],
        labels={},
        description="Test alert without namespace field"
    )


@patch("requests.post")
def test_adaptive_card_with_missing_namespace_using_dictget(mock_post, teams_provider, mock_response, alert_without_namespace):
    """Test Teams Adaptive Card handling missing namespace field using dictget function"""
    # Setup mock response
    mock_post.return_value = mock_response
    
    # Set the alert in context manager
    teams_provider.context_manager.set_event_context(alert_without_namespace)
    
    # Test with dictget function to handle missing namespace
    result = teams_provider.notify(
        typeCard="message",
        sections=[
            {
                "type": "TextBlock",
                "text": "🔔 **Test Alert**",
                "weight": "Bolder",
                "size": "Large"
            },
            {
                "type": "TextBlock", 
                "text": "**📦 Namespace**: keep.dictget({{ alert.labels }}, 'namespace', 'N/A')"
            },
            {
                "type": "TextBlock",
                "text": "**💥 Severity**: {{ alert.severity }}"
            }
        ]
    )
    
    # Verify the response
    assert result == {"response_text": "Success"}
    mock_post.assert_called_once()


@patch("requests.post") 
def test_adaptive_card_with_existing_namespace_using_dictget(mock_post, teams_provider, mock_response, alert_with_namespace):
    """Test Teams Adaptive Card handling existing namespace field using dictget function"""
    # Setup mock response
    mock_post.return_value = mock_response
    
    # Set the alert in context manager
    teams_provider.context_manager.set_event_context(alert_with_namespace)
    
    # Test with dictget function to handle existing namespace
    result = teams_provider.notify(
        typeCard="message",
        sections=[
            {
                "type": "TextBlock",
                "text": "🔔 **Test Alert**",
                "weight": "Bolder", 
                "size": "Large"
            },
            {
                "type": "TextBlock",
                "text": "**📦 Namespace**: keep.dictget({{ alert.labels }}, 'namespace', 'N/A')"
            },
            {
                "type": "TextBlock",
                "text": "**💥 Severity**: {{ alert.severity }}"
            }
        ]
    )
    
    # Verify the response
    assert result == {"response_text": "Success"}
    mock_post.assert_called_once()


@patch("requests.post")
def test_adaptive_card_with_mustache_conditionals(mock_post, teams_provider, mock_response, alert_without_namespace):
    """Test Teams Adaptive Card using mustache conditionals for missing fields"""
    # Setup mock response
    mock_post.return_value = mock_response
    
    # Set the alert in context manager  
    teams_provider.context_manager.set_event_context(alert_without_namespace)
    
    # Test with mustache conditionals for missing namespace
    result = teams_provider.notify(
        typeCard="message",
        sections=[
            {
                "type": "TextBlock",
                "text": "🔔 **{{ alert.name }}**",
                "weight": "Bolder",
                "size": "Large"
            },
            {
                "type": "TextBlock",
                "text": "**📦 Namespace**: {{#alert.labels.namespace}}{{ alert.labels.namespace }}{{/alert.labels.namespace}}{{^alert.labels.namespace}}N/A{{/alert.labels.namespace}}"
            },
            {
                "type": "TextBlock", 
                "text": "**💥 Severity**: {{ alert.severity }}"
            }
        ]
    )
    
    # Verify the response
    assert result == {"response_text": "Success"}
    mock_post.assert_called_once()


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


def test_github_issue_5070_mustache_template_rendering():
    """
    Test for GitHub issue #5070: Support conditional namespace display in Teams Adaptive Cards when label may be missing
    
    This test demonstrates the actual issue with mustache template rendering in the IOHandler.
    When using direct property access like {{ alert.labels.namespace }} and the field is missing,
    the template rendering fails with "Could not find key" error.
    """
    # Setup context manager with alert missing namespace
    context_manager = ContextManager(tenant_id="test-tenant", workflow_id="test-workflow")
    
    # Alert without namespace in labels
    alert_without_namespace = AlertDto(
        id="test-alert-1",
        name="Test Alert Without Namespace",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        message="Test alert message",
        source=["test"],
        labels={
            "service": "payments", 
            "environment": "prod"
            # Missing: namespace
        },
        lastReceived="2023-01-01T00:00:00Z"
    )
    
    context_manager.alert = alert_without_namespace
    context_manager.event_context = context_manager.alert
    iohandler = IOHandler(context_manager)
    
    # Test case 1: Direct property access should fail (this is the problem)
    template_with_direct_access = "Namespace: {{ alert.labels.namespace }}"
    
    with pytest.raises(RenderException) as exc_info:
        iohandler.render(template_with_direct_access, safe=True)
    
    assert "Could not find key" in str(exc_info.value)
    assert "alert.labels.namespace" in str(exc_info.value)
    print("✓ Confirmed: Direct property access fails when namespace is missing")
    
    # Test case 2: Using keep.dictget should work (this is the solution)
    template_with_dictget = "Namespace: keep.dictget({{ alert.labels }}, 'namespace', 'N/A')"
    
    rendered = iohandler.render(template_with_dictget, safe=True)
    assert "Namespace: N/A" in rendered
    print("✓ Confirmed: keep.dictget provides safe access with default values")
    
    # Test case 3: Mustache conditionals should work (alternative solution)
    template_with_conditionals = "Namespace: {{#alert.labels.namespace}}{{ alert.labels.namespace }}{{/alert.labels.namespace}}{{^alert.labels.namespace}}N/A{{/alert.labels.namespace}}"
    
    # Note: safe=False for mustache conditionals as per the iohandler logic
    rendered = iohandler.render(template_with_conditionals, safe=False)
    assert "Namespace: N/A" in rendered
    print("✓ Confirmed: Mustache conditionals provide safe access")
    
    # Test case 4: When namespace exists, all approaches should work
    alert_with_namespace = AlertDto(
        id="test-alert-2", 
        name="Test Alert With Namespace",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        message="Test alert message", 
        source=["test"],
        labels={
            "service": "payments",
            "environment": "prod", 
            "namespace": "production"
        },
        lastReceived="2023-01-01T00:00:00Z"
    )
    
    context_manager.alert = alert_with_namespace
    context_manager.event_context = context_manager.alert
    
    # Direct access should work when field exists
    rendered = iohandler.render("Namespace: {{ alert.labels.namespace }}", safe=True)
    assert "Namespace: production" in rendered
    
    # keep.dictget should also work
    rendered = iohandler.render("Namespace: keep.dictget({{ alert.labels }}, 'namespace', 'N/A')", safe=True)
    assert "Namespace: production" in rendered
    
    # Mustache conditionals should also work
    rendered = iohandler.render(template_with_conditionals, safe=False)
    assert "Namespace: production" in rendered
    
    print("✓ Confirmed: All approaches work when namespace field exists")


def test_teams_adaptive_card_safe_rendering_patterns(teams_provider, mock_response):
    """
    Test Teams provider with safe rendering patterns for missing fields
    """
    with patch("requests.post", return_value=mock_response) as mock_post:
        # Alert with partial data (missing namespace, pod, node)
        alert_with_partial_data = AlertDto(
            id="test-alert-3",
            name="Partial Data Alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.WARNING,
            message="Test alert with some missing fields",
            source=["kubernetes"],
            labels={
                "service": "web-api",
                "environment": "staging",
                # Missing: namespace, pod, node
            },
            lastReceived="2023-01-01T00:00:00Z",
        )
        
        # Teams Adaptive Card template using safe rendering patterns
        adaptive_card_template = [
            {
                "type": "TextBlock",
                "text": "**🚨 Alert**: {{ alert.name }}",
                "weight": "Bolder",
                "size": "Medium"
            },
            {
                "type": "TextBlock", 
                "text": "**📦 Service**: keep.dictget({{ alert.labels }}, 'service', 'Not specified')"
            },
            {
                "type": "TextBlock",
                "text": "**🌍 Environment**: keep.dictget({{ alert.labels }}, 'environment', 'Not specified')"
            },
            {
                "type": "TextBlock",
                "text": "**📦 Namespace**: keep.dictget({{ alert.labels }}, 'namespace', 'Not specified')"
            },
            {
                "type": "TextBlock",
                "text": "**🏠 Pod**: keep.dictget({{ alert.labels }}, 'pod', 'N/A')"
            },
            {
                "type": "TextBlock", 
                "text": "**🖥️ Node**: keep.dictget({{ alert.labels }}, 'node', 'N/A')"
            }
        ]
        
        # This should work without raising exceptions
        teams_provider.notify(
            message="Test notification",
            alert=alert_with_partial_data,
            typeCard="message", 
            sections=adaptive_card_template
        )
        
        # Verify the request was made
        assert mock_post.called
        call_data = mock_post.call_args[1]["json"]
        
        # Verify the template structure contains safe access patterns
        body_content = str(call_data["attachments"][0]["content"]["body"])
        assert "keep.dictget" in body_content  # Safe access function is used
        assert "namespace" in body_content  # Namespace field is referenced
        assert "service" in body_content  # Service field is referenced
        assert "environment" in body_content  # Environment field is referenced
        
        print("✓ Confirmed: Teams provider works with safe rendering patterns")


def test_render_context_safe_parameter_handling():
    """
    Test the render_context method's handling of safe parameters
    """
    context_manager = ContextManager(tenant_id="test-tenant", workflow_id="test-workflow")
    
    # Alert missing some fields
    alert_data = AlertDto(
        id="test-alert",
        name="Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.INFO,
        message="Test message",
        source=["test"],
        labels={
            "service": "api", 
            "environment": "prod"
            # Missing: namespace, pod
        },
        lastReceived="2023-01-01T00:00:00Z"
    )
    
    context_manager.alert = alert_data
    context_manager.event_context = context_manager.alert
    iohandler = IOHandler(context_manager)
    
    # Context to render with problematic templates
    context_to_render = {
        "safe_field": "keep.dictget({{ alert.labels }}, 'namespace', 'default')",
        "unsafe_field": "{{ alert.labels.namespace }}",  # This would fail with safe=True
        "existing_field": "{{ alert.labels.service }}"
    }
    
    # Test 1: Regular render_context (uses safe=True for strings)
    # This should fail on the unsafe_field
    with pytest.raises(RenderException):
        iohandler.render_context(context_to_render)
    
    # Test 2: Safe field should work
    safe_context = {"safe_field": "keep.dictget({{ alert.labels }}, 'namespace', 'default')"}
    rendered = iohandler.render_context(safe_context)
    assert "default" in rendered["safe_field"]
    
    # Test 3: Existing field should work 
    existing_context = {"existing_field": "{{ alert.labels.service }}"}
    rendered = iohandler.render_context(existing_context)
    assert "api" in rendered["existing_field"]
    
    print("✓ Confirmed: render_context handles safe/unsafe parameters correctly")
