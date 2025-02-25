import hashlib

import pytest

from keep.api.models.alert import AlertDto


def create_basic_alert(name, last_received):
    """Helper function to create AlertDto with minimal fields"""
    return AlertDto(
        name=name,
        lastReceived=last_received,
    )


def test_alert_dto_fingerprint_none():
    name = "Alert name"
    alert_dto = AlertDto(
        id="1234",
        name=name,
        status="firing",
        lastReceived="2021-01-01T00:00:00.000Z",
        environment="production",
        isDuplicate=False,
        duplicateReason=None,
        service="backend",
        source=["keep"],
        message="Alert message",
        description="Alert description",
        severity="critical",
        pushed=True,
        event_id="1234",
        url="https://www.google.com/search?q=open+source+alert+management",
    )
    assert alert_dto.fingerprint == hashlib.sha256(name.encode()).hexdigest()


def test_alert_dto_basic_iso_timestamp():
    """Test with standard ISO timestamp"""
    alert = create_basic_alert(
        name="Test Alert", last_received="2024-02-15T12:34:56.789Z"
    )
    assert alert.lastReceived == "2024-02-15T12:34:56.789Z"
    assert alert.fingerprint == hashlib.sha256("Test Alert".encode()).hexdigest()


def test_alert_dto_unix_timestamp():
    """Test with UNIX timestamp"""
    alert = create_basic_alert(name="Unix Alert", last_received="1739550225.735604345Z")
    # The expected ISO format for this Unix timestamp
    assert alert.lastReceived.endswith("Z")
    assert alert.fingerprint == hashlib.sha256("Unix Alert".encode()).hexdigest()


def test_alert_dto_unix_timestamp_no_z():
    """Test with UNIX timestamp without Z suffix"""
    alert = create_basic_alert(
        name="Unix Alert No Z", last_received="1739550225.735604345"
    )
    assert alert.lastReceived.endswith("Z")
    assert alert.fingerprint == hashlib.sha256("Unix Alert No Z".encode()).hexdigest()


def test_alert_dto_empty_timestamp():
    """Test with empty timestamp (should use current time)"""
    alert = create_basic_alert(name="Current Time Alert", last_received=None)
    # Verify it's in ISO format and ends with Z
    assert alert.lastReceived.endswith("Z")
    assert "T" in alert.lastReceived
    assert (
        alert.fingerprint == hashlib.sha256("Current Time Alert".encode()).hexdigest()
    )


def test_alert_dto_invalid_timestamp():
    """Test with invalid timestamp format"""
    with pytest.raises(ValueError, match="Invalid date format:"):
        create_basic_alert(name="Invalid Time Alert", last_received="not-a-timestamp")


def test_alert_dto_different_timezone():
    """Test with non-UTC timezone"""
    alert = create_basic_alert(
        name="Timezone Alert", last_received="2024-02-15T12:34:56.789+05:00"
    )
    # Should be converted to UTC
    assert alert.lastReceived.endswith("Z")
    assert alert.fingerprint == hashlib.sha256("Timezone Alert".encode()).hexdigest()


def test_alert_dto_microsecond_precision():
    """Test timestamp with different microsecond precision"""
    alert = create_basic_alert(
        name="Precision Alert", last_received="1739550225.735604"  # Less precision
    )
    assert alert.lastReceived.endswith("Z")
    assert "." in alert.lastReceived  # Should still include milliseconds
    assert alert.fingerprint == hashlib.sha256("Precision Alert".encode()).hexdigest()


def test_alert_dto_additional_formats():
    """Test various additional timestamp formats"""
    test_cases = [
        # Unix timestamps with different precisions
        ("1739550225", "Unix Integer"),  # Integer timestamp
        ("1739550225.0", "Unix Float"),  # Float with no decimal
        ("1739550225.7", "Unix Single Decimal"),  # Single decimal
        ("1739550225.73560434599999", "Unix Long Decimal"),  # Extra long decimal
        # ISO formats with different precisions
        ("2024-02-15T12:34:56Z", "ISO No Milliseconds"),  # No milliseconds
        (
            "2024-02-15T12:34:56.1Z",
            "ISO Single Millisecond",
        ),  # Single digit millisecond
        ("2024-02-15T12:34:56.12Z", "ISO Two Milliseconds"),  # Two digit millisecond
        ("2024-02-15T12:34:56.123456789Z", "ISO Microseconds"),  # Extra precision
        # Different timezone formats
        ("2024-02-15T12:34:56.789+00:00", "UTC Explicit"),  # Explicit UTC
        ("2024-02-15T12:34:56.789-00:00", "UTC Negative"),  # Negative UTC
        ("2024-02-15T12:34:56.789+14:00", "UTC Edge Plus"),  # UTC+14 (furthest ahead)
        ("2024-02-15T12:34:56.789-12:00", "UTC Edge Minus"),  # UTC-12 (furthest behind)
        # Edge cases
        ("1739550225.000000000Z", "Unix All Zeros"),  # All zero decimals
        ("1739550225.999999999Z", "Unix All Nines"),  # All nine decimals
        ("2024-02-29T23:59:59.999Z", "Leap Year"),  # Leap year edge
        ("2024-12-31T23:59:59.999Z", "Year End"),  # Year end
        ("2024-01-01T00:00:00.000Z", "Year Start"),  # Year start
        # Special cases
        ("2024-02-15 12:34:56.789Z", "Space Separator"),  # Space instead of T
        ("2024-02-15T12:34:56.789", "No Z"),  # Missing Z
    ]

    for timestamp, name in test_cases:
        try:
            alert = create_basic_alert(name=name, last_received=timestamp)
            # Verify basic format requirements
            assert alert.lastReceived.endswith("Z")
            assert "T" in alert.lastReceived
            assert alert.fingerprint == hashlib.sha256(name.encode()).hexdigest()
        except ValueError as e:
            pytest.fail(
                f"Failed to parse timestamp {timestamp} for case {name}: {str(e)}"
            )


def test_alert_dto_invalid_timestamps():
    """Test various invalid timestamp formats"""
    invalid_cases = [
        "not-a-timestamp",  # Completely invalid
        "2024-13-15T12:34:56.789Z",  # Invalid month
        "2024-02-30T12:34:56.789Z",  # Invalid day
        "2024-02-15T25:34:56.789Z",  # Invalid hour
        "2024-02-15T12:60:56.789Z",  # Invalid minute
        "2024-02-15T12:34:61.789Z",  # Invalid second
        "1739550225.ABCZ",  # Invalid decimal
        "2024-02-15T12:34:56.789+",  # Incomplete timezone
        "2024-02-15T12:34:56.789+00:",  # Malformed timezone
    ]

    for timestamp in invalid_cases:
        with pytest.raises(ValueError, match="Invalid date format:|Out of range"):
            try:
                create_basic_alert(name="Invalid Format Test", last_received=timestamp)
            except ValueError:
                raise
            # if no error, fail the test
            pytest.fail(f"Expected ValueError for timestamp {timestamp}")
