from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.utils.enrichment_helpers import calculated_firing_counter


def test_firing_counter_first_alert():
    """Test that the first alert has a firing counter of 1."""
    # Create a new alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # No previous alert
    previous_alert = None

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter is 1 for the first alert
    assert counter == 1


def test_firing_counter_increment():
    """Test that the firing counter increments for consecutive firing alerts."""
    # Create a current alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Create a previous alert with an existing firing counter
    previous_alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
        firingCounter=3,
    )

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter increments by 1
    assert counter == 4


def test_firing_counter_acknowledged():
    """Test that acknowledged alerts have a firing counter of 0."""
    # Create an acknowledged alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.ACKNOWLEDGED.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Create a previous alert with an existing firing counter
    previous_alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
        firingCounter=5,
    )

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter is 0 for acknowledged alerts
    assert counter == 0


def test_firing_counter_previous_list():
    """Test that the function works when previous_alert is a list."""
    # Create a current alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Create a previous alert as list
    previous_alert = [
        AlertDto(
            name="Test Alert",
            status=AlertStatus.FIRING.value,
            source=["test"],
            fingerprint="test-fingerprint",
            firingCounter=7,
        )
    ]

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter increments by 1
    assert counter == 8


def test_firing_counter_resolved_to_firing():
    """Test counter when alert transitions from resolved to firing again."""
    # Create a current firing alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Create a previous resolved alert
    previous_alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.RESOLVED.value,
        source=["test"],
        fingerprint="test-fingerprint",
        firingCounter=10,
    )

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter increments by 1 even after resolved
    assert counter == 11


def test_firing_counter_empty_list():
    """Test handling of empty list as previous alert."""
    # Create a current alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Empty list as previous alert
    previous_alert = []

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter is 1 for empty list (same as None)
    assert counter == 1


def test_firing_counter_resolved_status():
    """ONLY ACKNOWLEDGED ALERTS SHOULD HAVE A FIRING COUNTER OF 0"""
    # Create a resolved alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.RESOLVED.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Create a previous alert with an existing firing counter
    previous_alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
        firingCounter=5,
    )

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter is 0 for resolved alerts
    assert counter == 6


def test_firing_counter_multiple_previous_alerts():
    """Test with multiple previous alerts where one matches the fingerprint."""
    # Create a current alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Create multiple previous alerts as a list
    previous_alert = [
        AlertDto(
            name="Test Alert",
            status=AlertStatus.FIRING.value,
            source=["test"],
            fingerprint="test-fingerprint",
            firingCounter=9,
        )
    ]

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter increments based on the matching fingerprint
    assert counter == 10


def test_firing_counter_acknowledged_to_firing():
    """Test counter when alert transitions from acknowledged to firing again."""
    # Create a current firing alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Create a previous acknowledged alert
    previous_alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.ACKNOWLEDGED.value,
        source=["test"],
        fingerprint="test-fingerprint",
        firingCounter=0,
    )

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter starts at 1 again after acknowledged
    assert counter == 1


def test_firing_counter_no_previous_counter():
    """Test when previous alert exists but has no firing counter."""
    # Create a current alert
    alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Create a previous alert without a firing counter
    previous_alert = AlertDto(
        name="Test Alert",
        status=AlertStatus.FIRING.value,
        source=["test"],
        fingerprint="test-fingerprint",
    )

    # Calculate firing counter
    counter = calculated_firing_counter(alert, previous_alert)

    # Assert that the counter starts at 1 when previous has no counter
    assert counter == 1
