import xml.etree.ElementTree as ET
from datetime import datetime
from unittest.mock import patch

import pytest
from pydantic import AnyHttpUrl

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.routes.preset import _generate_rss_feed
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


def test_generate_rss_feed_empty():
    """Test RSS feed generation with no alerts"""
    rss_content = _generate_rss_feed([], "test-preset", "http://localhost:8080")
    
    # Parse XML to validate structure
    root = ET.fromstring(rss_content)
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    
    channel = root.find("channel")
    assert channel is not None
    
    title_element = channel.find("title")
    assert title_element is not None
    title = title_element.text
    assert title and "Keep Alerts - test-preset" in title
    
    # Should have no items
    items = channel.findall("item")
    assert len(items) == 0


def test_generate_rss_feed_with_alerts():
    """Test RSS feed generation with sample alerts"""
    # Create test alerts
    alerts = [
        AlertDto(
            id="alert-1",
            name="Test Alert 1",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived="2023-01-01T12:00:00.000Z",
            environment="production",
            source=["prometheus"],
            description="Test alert description",
            service="web-service",
            url=AnyHttpUrl("https://example.com/alert/1"),
            fingerprint="fp-1"
        ),
        AlertDto(
            id="alert-2", 
            name="Test Alert 2",
            status=AlertStatus.RESOLVED,
            severity=AlertSeverity.WARNING,
            lastReceived="2023-01-01T11:00:00.000Z",
            environment="staging",
            source=["grafana", "loki"],
            description="Another test alert",
            fingerprint="fp-2"
        )
    ]
    
    rss_content = _generate_rss_feed(alerts, "test-preset", "http://localhost:8080")
    
    # Parse XML to validate structure
    root = ET.fromstring(rss_content)
    assert root.tag == "rss"
    
    channel = root.find("channel")
    assert channel is not None
    
    # Check channel metadata
    title_element = channel.find("title")
    assert title_element is not None
    title = title_element.text
    assert title and "Keep Alerts - test-preset" in title
    
    description_element = channel.find("description")
    assert description_element is not None
    description = description_element.text
    assert description and "Alert feed for test-preset preset" in description
    
    # Should have two items
    items = channel.findall("item")
    assert len(items) == 2
    
    # Check first alert item
    item1 = items[0]
    item1_title_element = item1.find("title")
    assert item1_title_element is not None
    item1_title = item1_title_element.text
    assert item1_title and "[CRITICAL] Test Alert 1 (FIRING)" in item1_title
    
    item1_desc_element = item1.find("description")
    assert item1_desc_element is not None
    item1_desc = item1_desc_element.text
    assert item1_desc and "Test alert description" in item1_desc
    assert "Environment: production" in item1_desc
    assert "Source: prometheus" in item1_desc
    assert "Service: web-service" in item1_desc
    
    item1_link_element = item1.find("link")
    assert item1_link_element is not None
    item1_link = item1_link_element.text
    assert item1_link == "https://example.com/alert/1"
    
    item1_guid_element = item1.find("guid")
    assert item1_guid_element is not None
    item1_guid = item1_guid_element.text
    assert item1_guid == "fp-1"
    
    item1_category_element = item1.find("category")
    assert item1_category_element is not None
    item1_category = item1_category_element.text
    assert item1_category == "critical"
    
    # Check second alert item
    item2 = items[1]
    item2_title_element = item2.find("title")
    assert item2_title_element is not None
    item2_title = item2_title_element.text
    assert item2_title and "[WARNING] Test Alert 2 (RESOLVED)" in item2_title
    
    item2_desc_element = item2.find("description")
    assert item2_desc_element is not None
    item2_desc = item2_desc_element.text
    assert item2_desc and "Another test alert" in item2_desc
    assert "Environment: staging" in item2_desc
    assert "Source: grafana, loki" in item2_desc
    
    # Should use default link when no URL provided
    item2_link_element = item2.find("link")
    assert item2_link_element is not None
    item2_link = item2_link_element.text
    assert item2_link == "http://localhost:8080/alerts/feed"


def test_generate_rss_feed_minimal_alert():
    """Test RSS feed generation with minimal alert data"""
    alerts = [
        AlertDto(
            id="minimal-alert",
            name="Minimal Alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.INFO,
            lastReceived="2023-01-01T12:00:00.000Z",
            fingerprint="minimal-fp"
        )
    ]
    
    rss_content = _generate_rss_feed(alerts, "minimal-preset", "http://localhost:8080")
    
    # Parse XML to validate structure
    root = ET.fromstring(rss_content)
    channel = root.find("channel")
    assert channel is not None
    items = channel.findall("item")
    assert len(items) == 1
    
    item = items[0]
    title_element = item.find("title")
    assert title_element is not None
    title = title_element.text
    assert title and "[INFO] Minimal Alert (FIRING)" in title
    
    # Should handle missing description gracefully
    description_element = item.find("description")
    assert description_element is not None
    description = description_element.text
    assert description and "No description available" in description


def test_generate_rss_feed_special_characters():
    """Test RSS feed generation with special characters that need escaping"""
    alerts = [
        AlertDto(
            id="special-alert",
            name="Alert with <special> & characters",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived="2023-01-01T12:00:00.000Z",
            description="Description with <html> & special characters",
            fingerprint="special-fp"
        )
    ]
    
    rss_content = _generate_rss_feed(alerts, "test & special <preset>", "http://localhost:8080")
    
    # Parse XML to validate structure - should not raise XML parsing errors
    root = ET.fromstring(rss_content)
    channel = root.find("channel")
    assert channel is not None
    
    # Check that special characters are properly escaped
    title_element = channel.find("title")
    assert title_element is not None
    title = title_element.text
    assert title and "test &amp; special &lt;preset&gt;" in title
    
    items = channel.findall("item")
    item = items[0]
    item_title_element = item.find("title")
    assert item_title_element is not None
    item_title = item_title_element.text
    assert item_title and "&lt;special&gt; &amp; characters" in item_title
    
    item_desc_element = item.find("description")
    assert item_desc_element is not None
    item_desc = item_desc_element.text
    assert item_desc and "&lt;html&gt; &amp; special characters" in item_desc


def test_rss_feed_endpoint_feed_preset(client, setup_api_key):
    """Test the RSS feed endpoint with the feed preset"""
    # This test will fail without the implementation and pass with it
    response = client.get("/preset/feed/rss", headers={"x-api-key": setup_api_key})
    
    # Should return 200 and RSS content
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/rss+xml; charset=utf-8"
    
    # Validate XML structure
    root = ET.fromstring(response.content)
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    
    channel = root.find("channel")
    assert channel is not None
    
    title_element = channel.find("title")
    assert title_element is not None
    title = title_element.text
    assert title and "Keep Alerts - feed" in title


def test_rss_feed_endpoint_nonexistent_preset(client, setup_api_key):
    """Test the RSS feed endpoint with a non-existent preset"""
    response = client.get("/preset/nonexistent/rss", headers={"x-api-key": setup_api_key})
    
    # Should return 404
    assert response.status_code == 404


def test_rss_feed_endpoint_unauthorized(client):
    """Test the RSS feed endpoint without authentication"""
    response = client.get("/preset/feed/rss")
    
    # Should return 401 or 403 (depending on auth setup)
    assert response.status_code in [401, 403]


def test_rss_feed_pub_date_formatting():
    """Test that publication dates are formatted correctly"""
    alerts = [
        AlertDto(
            id="date-test-alert",
            name="Date Test Alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.INFO,
            lastReceived="2023-06-15T14:30:00.000Z",
            fingerprint="date-fp"
        )
    ]
    
    rss_content = _generate_rss_feed(alerts, "date-test", "http://localhost:8080")
    
    root = ET.fromstring(rss_content)
    channel = root.find("channel")
    assert channel is not None
    items = channel.findall("item")
    item = items[0]
    
    pub_date_element = item.find("pubDate")
    assert pub_date_element is not None
    pub_date = pub_date_element.text
    # Should be in RFC 2822 format: "Thu, 15 Jun 2023 14:30:00 GMT"
    assert pub_date and "15 Jun 2023" in pub_date
    assert "GMT" in pub_date