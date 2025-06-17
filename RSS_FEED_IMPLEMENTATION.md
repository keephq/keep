# RSS Feed Implementation for Keep Alerts

This document describes the implementation of a basic RSS feed for Keep alert management platform, addressing GitHub issue #5047.

## Overview

A new RSS feed endpoint has been added to provide a "very crude and bare-bones RSS feed" for alerts from any preset in the Keep platform. This allows users to subscribe to alert feeds using RSS readers or other RSS-consuming applications.

## Implementation Details

### New Endpoint

**URL**: `GET /preset/{preset_name}/rss`

**Description**: Returns an RSS XML feed containing alerts from the specified preset.

**Authentication**: Requires valid API key or authentication token (same as other preset endpoints).

**Response**: 
- Content-Type: `application/rss+xml; charset=utf-8`
- Body: Valid RSS 2.0 XML feed

### Features

1. **RSS 2.0 Compliance**: Generates valid RSS 2.0 XML feeds
2. **Alert Mapping**: Maps alert properties to RSS elements:
   - Alert name, severity, and status → RSS item title
   - Alert description, environment, source, service → RSS item description
   - Alert URL or fallback link → RSS item link
   - Alert fingerprint → RSS item GUID
   - Alert lastReceived → RSS item publication date
   - Alert severity → RSS item category

3. **XML Escaping**: Properly escapes special characters (< > & etc.) in XML content
4. **Error Handling**: Returns 404 for non-existent presets, proper authentication errors
5. **Performance**: Uses background tasks for alert gathering to avoid blocking responses

### Code Structure

#### New Functions in `keep/api/routes/preset.py`:

1. **`_generate_rss_feed(alerts, preset_name, base_url)`**
   - Converts list of AlertDto objects to RSS XML string
   - Handles XML escaping and proper RSS formatting
   - Maps alert fields to appropriate RSS elements

2. **`get_preset_rss_feed()`**
   - FastAPI endpoint handler for RSS feed requests
   - Handles authentication, preset validation, and alert retrieval
   - Returns FastAPI Response with proper content type

### Test Coverage

Comprehensive unit tests in `tests/test_rss_feed.py` cover:

1. **RSS Generation Tests**:
   - Empty alert lists
   - Multiple alerts with full data
   - Minimal alert data
   - Special character escaping
   - Date formatting validation

2. **Endpoint Integration Tests**:
   - Valid preset access
   - Non-existent preset handling
   - Authentication validation
   - Response format validation

### Usage Examples

#### Basic Usage
```bash
# Get RSS feed for the default "feed" preset
curl -H "x-api-key: your-api-key" \
  http://your-keep-instance/preset/feed/rss

# Get RSS feed for a custom preset
curl -H "x-api-key: your-api-key" \
  http://your-keep-instance/preset/my-custom-preset/rss
```

#### Sample RSS Output
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Keep Alerts - feed</title>
<description>Alert feed for feed preset</description>
<link>http://your-keep-instance</link>
<language>en-us</language>
<lastBuildDate>Thu, 21 Dec 2023 14:30:00 GMT</lastBuildDate>
<generator>Keep Alert Management Platform</generator>
<item>
<title>[CRITICAL] Database Connection Failed (FIRING)</title>
<description>Database connection timeout occurred | Environment: production | Source: prometheus | Service: backend</description>
<link>http://your-keep-instance/alerts/feed</link>
<guid isPermaLink="false">db-connection-failed-fingerprint</guid>
<pubDate>Thu, 21 Dec 2023 14:25:00 GMT</pubDate>
<category>critical</category>
</item>
</channel>
</rss>
```

## Test Scenarios

### Tests That Should Fail Without Implementation
1. `test_rss_feed_endpoint_feed_preset` - Accessing `/preset/feed/rss` should return 404 without the new endpoint
2. `test_generate_rss_feed_*` - RSS generation functions don't exist without implementation

### Tests That Should Pass With Implementation
1. All RSS generation tests validate proper XML structure and content
2. Endpoint tests validate authentication, error handling, and response format
3. Special character escaping tests ensure XML safety

## Benefits

1. **RSS Reader Integration**: Users can monitor alerts in their preferred RSS readers
2. **External Tool Integration**: Other systems can consume alert feeds via RSS
3. **Real-time Monitoring**: RSS feeds provide near real-time alert updates
4. **Preset Flexibility**: Any existing or custom preset can be accessed as RSS feed
5. **Standards Compliance**: Uses standard RSS 2.0 format for maximum compatibility

## Future Enhancements

Potential improvements for future versions:
1. RSS feed pagination for large alert volumes
2. RSS feed filtering parameters (severity, status, etc.)
3. ATOM feed format support
4. RSS feed caching for performance
5. RSS feed analytics and metrics