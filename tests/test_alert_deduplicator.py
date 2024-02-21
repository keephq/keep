from keep.api.alert_deduplicator.alert_deduplicator import AlertDeduplicator
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.alert import Alert, AlertDeduplicationFilter

# Mocked filter data
filters = [
    {"id": 1, "matcher_cel": 'source == "sensorA"', "fields": ["field_to_remove_1"]},
    {"id": 2, "matcher_cel": 'source == "sensorB"', "fields": ["field_to_remove_2"]},
]

# Mocked alerts for testing
alerts = []


def test_deduplication_sanity(db_session):
    deduplicator = AlertDeduplicator(SINGLE_TENANT_UUID)
    alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="grafana-test-alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived="2021-08-01T00:00:00Z",
    )
    alert_hash, deduplicated = deduplicator.is_deduplicated(alert)
    # shouldn't be deduplicated
    assert not deduplicated
    # now add it to the db
    db_session.add(
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event=alert.dict(),
            fingerprint="test",
            alert_hash=alert_hash,
        )
    )
    db_session.commit()
    # Now let's re run it - should be deduplicated
    _, deduplicated = deduplicator.is_deduplicated(alert)
    assert deduplicated


def test_deduplication_with_matcher(db_session):
    # add the matcher:
    matcher = AlertDeduplicationFilter(
        tenant_id=SINGLE_TENANT_UUID,
        matcher_cel='source[0] == "grafana"',
        fields=["labels.some-non-relevant-field-2"],
    )
    db_session.add(matcher)
    db_session.commit()
    # now let's run the deduplicator
    deduplicator = AlertDeduplicator(SINGLE_TENANT_UUID)
    alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="grafana-test-alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived="2021-08-01T00:00:00Z",
        labels={
            "some-non-relevant-field-1": "1234",
            "some-non-relevant-field-2": "4321",
        },
    )
    alert_hash, deduplicated = deduplicator.is_deduplicated(alert)
    # sanity - shouldn't be deduplicated
    assert not deduplicated
    # now add it to the db
    db_session.add(
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event=alert.dict(),
            fingerprint="test",
            alert_hash=alert_hash,
        )
    )
    db_session.commit()
    # Now let's re run it - should not be deduplicated (since some-non-relevant-field-1 is not in fields)
    alert.labels["some-non-relevant-field-1"] = "1111"
    _, deduplicated = deduplicator.is_deduplicated(alert)
    # Shouldn't be deduplicated since some-non-relevant-field-1 changed
    #   and it is not the field we are removing in filter
    assert not deduplicated
    # Now let's re run it - should be deduplicated
    alert.labels["some-non-relevant-field-1"] = "1234"
    alert.labels["some-non-relevant-field-2"] = "1111"
    alert_hash, deduplicated = deduplicator.is_deduplicated(alert)
    # Should be deduplicated since some-non-relevant-field-2 changed
    #   and it is the field we are removing in filter
    assert deduplicated


def test_deduplication_with_unrelated_filter(db_session):
    # add the matcher:
    matcher = AlertDeduplicationFilter(
        tenant_id=SINGLE_TENANT_UUID,
        matcher_cel='source[0] == "grafana"',
        fields=["labels.some-non-relevant-field"],
    )
    db_session.add(matcher)
    db_session.commit()
    # now let's run the deduplicator
    deduplicator = AlertDeduplicator(SINGLE_TENANT_UUID)
    alert = AlertDto(
        id="grafana-1",
        source=["not-grafana"],
        name="grafana-test-alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived="2021-08-01T00:00:00Z",
        labels={
            "some-non-relevant-field": "1234",
        },
    )
    alert_hash, deduplicated = deduplicator.is_deduplicated(alert)
    # sanity - shouldn't be deduplicated anyway
    assert not deduplicated
    # now add it to the db
    db_session.add(
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event=alert.dict(),
            fingerprint="test",
            alert_hash=alert_hash,
        )
    )
    db_session.commit()
    # Let's change the non relevant field and re run it - should not be deduplicated
    #   since the filter does not match
    alert.labels["some-non-relevant-field"] = "1111"
    _, deduplicated = deduplicator.is_deduplicated(alert)
    # Shouldn't be deduplicated since some-non-relevant-field-1 changed
    #   and it is not the field we are removing in filter
    assert not deduplicated
