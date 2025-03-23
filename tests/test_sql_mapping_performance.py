import random
import string
import time

import pytest
from sqlmodel import Session

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.cel_to_sql.mapping_rule_matcher import MappingRuleMatcher
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.mapping import MappingRule
from tests.fixtures.client import test_app  # noqa


def random_string(length=10):
    """Generate a random string."""
    return "".join(random.choice(string.ascii_letters) for _ in range(length))


@pytest.fixture
def large_mapping_rule(db_session: Session):
    """Create a mapping rule with a large number of rows."""
    # Generate 1000 rows with unique keys and values
    rows = []
    for i in range(1000):
        rows.append(
            {
                "customer_id": f"customer-{i:04d}",
                "name": f"Customer {i}",
                "email": f"customer{i}@example.com",
                "phone": f"555-{i:04d}",
                "type": random.choice(["enterprise", "smb", "startup"]),
                "region": random.choice(["us-east", "us-west", "eu", "asia"]),
                "tier": random.choice(["free", "basic", "premium", "enterprise"]),
                "support_level": random.choice(["basic", "standard", "premium"]),
                "account_manager": random_string(),
                "metadata": random_string(20),
            }
        )

    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Large Customer Dataset",
        description="A rule with many customer records",
        matchers=[["customer_id"]],
        rows=rows,
        type="csv",
        file_name="",
        created_by="test",
        condition="",
        new_property_name="",
        prefix_to_remove="",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def large_multi_level_rule(db_session: Session):
    """Create a multi-level mapping rule with a large number of rows."""
    # Generate 1000 rows with unique keys and values
    rows = []
    for i in range(1000):
        service_id = f"service-{i}"
        rows.append(
            {
                "service_id": service_id,
                "name": f"Service {i}",
                "owner": f"team-{i % 20}",
                "status": random.choice(["active", "deprecated", "in-development"]),
                "url": f"https://service-{i}.example.com",
                "port": 8000 + i % 1000,
                "version": f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
                "dependencies": random_string(),
                "description": random_string(30),
            }
        )

    rule = MappingRule(
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        name="Large Service Dataset",
        description="A multi-level rule with many service records",
        matchers=[["services"]],
        rows=rows,
        type="csv",
        is_multi_level=True,
        new_property_name="service_info",
        file_name="",
        created_by="test",
        condition="",
        prefix_to_remove="",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


def test_large_dataset_performance(
    db_session: Session, large_mapping_rule: MappingRule
):
    """Test performance with a large dataset."""
    dialect_name = None
    if (
        hasattr(db_session, "bind")
        and db_session.bind is not None
        and hasattr(db_session.bind, "dialect")
    ):
        dialect_name = db_session.bind.dialect.name

    matcher = MappingRuleMatcher(dialect_name=dialect_name, session=db_session)

    # Test case 1: Match an item at the beginning of the dataset
    start_time = time.time()
    alert_values = {"customer_id": "customer-10"}
    matched_row = matcher.get_matching_row(large_mapping_rule, alert_values)
    beginning_time = time.time() - start_time

    assert matched_row is not None
    assert matched_row["name"] == "Customer 10"

    # Test case 2: Match an item in the middle of the dataset
    start_time = time.time()
    alert_values = {"customer_id": "customer-500"}
    matched_row = matcher.get_matching_row(large_mapping_rule, alert_values)
    middle_time = time.time() - start_time

    assert matched_row is not None
    assert matched_row["name"] == "Customer 500"

    # Test case 3: Match an item at the end of the dataset
    start_time = time.time()
    alert_values = {"customer_id": "customer-990"}
    matched_row = matcher.get_matching_row(large_mapping_rule, alert_values)
    end_time = time.time() - start_time

    assert matched_row is not None
    assert matched_row["name"] == "Customer 990"

    # Test case 4: No match
    start_time = time.time()
    alert_values = {"customer_id": "non-existent"}
    matched_row = matcher.get_matching_row(large_mapping_rule, alert_values)
    no_match_time = time.time() - start_time

    assert matched_row is None

    # Log performance metrics
    print("\nPerformance metrics for large dataset (1000 rows):")
    print(f"Beginning match time: {beginning_time:.6f} seconds")
    print(f"Middle match time: {middle_time:.6f} seconds")
    print(f"End match time: {end_time:.6f} seconds")
    print(f"No match time: {no_match_time:.6f} seconds")

    # Assert that all operations are reasonably fast (< 0.1 seconds)
    # Adjust this threshold as needed based on your environment
    assert beginning_time < 0.1, "Beginning match too slow"
    assert middle_time < 0.1, "Middle match too slow"
    assert end_time < 0.1, "End match too slow"
    assert no_match_time < 0.1, "No match case too slow"


def test_multi_level_large_dataset_performance(
    db_session: Session, large_multi_level_rule: MappingRule
):
    """Test multi-level mapping performance with a large dataset."""
    dialect_name = None
    if (
        hasattr(db_session, "bind")
        and db_session.bind is not None
        and hasattr(db_session.bind, "dialect")
    ):
        dialect_name = db_session.bind.dialect.name

    matcher = MappingRuleMatcher(dialect_name=dialect_name, session=db_session)

    # Generate a list of 100 service IDs to match
    service_ids = [f"service-{i}" for i in random.sample(range(1000), 100)]

    # Test multi-level matching performance
    start_time = time.time()
    matches = matcher.get_matching_rows_multi_level(
        large_multi_level_rule, "service_id", service_ids
    )
    multi_level_time = time.time() - start_time

    assert len(matches) == 100
    for service_id in service_ids:
        assert service_id in matches
        assert "name" in matches[service_id]
        assert "owner" in matches[service_id]

    # Log performance metrics
    print("\nMulti-level matching performance (100 matches out of 1000 rows):")
    print(f"Matching time: {multi_level_time:.6f} seconds")

    # Assert that the operation is reasonably fast (< 0.5 seconds)
    # Multi-level matching will be slower than single matches
    assert multi_level_time < 0.5, "Multi-level matching too slow"


def test_comparison_with_fallback(db_session: Session, large_mapping_rule: MappingRule):
    """Compare SQL-based matching with fallback Python implementation."""
    dialect_name = None
    if (
        hasattr(db_session, "bind")
        and db_session.bind is not None
        and hasattr(db_session.bind, "dialect")
    ):
        dialect_name = db_session.bind.dialect.name

    matcher = MappingRuleMatcher(dialect_name=dialect_name, session=db_session)

    # Test with SQL-based matching
    start_time = time.time()
    alert_values = {"customer_id": "customer-0534"}
    sql_matched_row = matcher.get_matching_row(large_mapping_rule, alert_values)
    sql_time = time.time() - start_time

    # Test with fallback Python implementation
    start_time = time.time()
    fallback_matched_row = matcher._fallback_get_matching_row(
        large_mapping_rule, alert_values
    )
    fallback_time = time.time() - start_time

    # Verify both methods return the same result
    assert sql_matched_row is not None
    assert fallback_matched_row is not None
    assert sql_matched_row["name"] == fallback_matched_row["name"]

    # Log performance comparison
    print("\nSQL vs. Fallback performance comparison:")
    print(f"SQL-based match time: {sql_time:.6f} seconds")
    print(f"Fallback match time: {fallback_time:.6f} seconds")
    print(f"Speed improvement: {fallback_time / sql_time:.2f}x")

    # Assert that SQL is faster than fallback
    # The difference should be significant for large datasets
    assert sql_time < fallback_time, "SQL-based matching should be faster than fallback"


def test_end_to_end_performance(db_session: Session, large_mapping_rule: MappingRule):
    """Test end-to-end performance using EnrichmentsBl."""
    # Create alert dto
    alert = AlertDto(
        id="test-id",
        name="Test Alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.HIGH,
        lastReceived="2023-01-01T00:00:00Z",
        source=["test-source"],
        fingerprint="test-fingerprint",
    )

    # Add customer_id as a dynamic attribute
    setattr(alert, "customer_id", "customer-500")  # Match with row in the middle

    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=db_session)

    # Time the full enrichment process
    start_time = time.time()
    result = enrichment_bl.check_if_match_and_enrich(alert, large_mapping_rule)
    end_to_end_time = time.time() - start_time

    # Verify enrichment worked
    assert result is True
    assert hasattr(alert, "name")
    assert hasattr(alert, "email")
    assert hasattr(alert, "phone")

    # Log end-to-end performance
    print("\nEnd-to-end enrichment performance:")
    print(f"Enrichment time: {end_to_end_time:.6f} seconds")

    # Assert reasonable performance for end-to-end process
    assert end_to_end_time < 0.2, "End-to-end enrichment too slow"
