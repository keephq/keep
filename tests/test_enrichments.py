# test_enrichments.py
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import AlertActionType
from keep.api.models.db.extraction import ExtractionRule
from keep.api.models.db.mapping import MappingRule
from keep.api.models.db.topology import TopologyService
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


@pytest.fixture(autouse=True)
def patch_get_tenants_configurations():
    """Automatically patch get_tenants_configurations for all tests."""
    with patch(
        "keep.api.core.tenant_configuration.TenantConfiguration._TenantConfiguration.get_configuration",
        return_value=None,
    ):
        yield


@pytest.fixture
def mock_session():
    """Create a mock session to simulate database operations."""
    session = MagicMock()
    query_mock = MagicMock()
    session.query.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.all.return_value = []  # Default to no rules, override in specific tests
    # Patch the get_tenants_configurations function
    return session


@pytest.fixture
def mock_alert_dto():
    """Fixture for creating a mock AlertDto."""
    return AlertDto(
        id="test_id",
        name="Test Alert",
        status="firing",
        severity="high",
        lastReceived="2021-01-01T00:00:00Z",
        source=["test_source"],
        fingerprint="mock_fingerprint",
        labels={},
    )


@pytest.mark.asyncio
async def test_run_extraction_rules_no_rules_applies(mock_session, mock_alert_dto, db_session):
    # Assuming there are no extraction rules
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = (
        []
    )
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)
    result_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    # Check that the event has not changed (no rules to apply)
    assert result_event == mock_alert_dto  # Assuming no change if no rules


@pytest.mark.asyncio
def test_run_extraction_rules_regex_named_groups(mock_session, mock_alert_dto, db_session):
    # Setup an extraction rule that should apply based on the alert content
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ name }}",
        regex="(?P<service_name>Test) (?P<alert_type>Alert)",
        disabled=False,
        pre=True,
        condition=None,  # No condition for simplicity
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Mocking chevron rendering to simulate template rendering
    with patch("chevron.render", return_value="Test Alert"):
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    # Assert that the event is now enriched with regex group names
    assert enriched_event.service_name == "Test"
    assert enriched_event.alert_type == "Alert"


@pytest.mark.asyncio
def test_run_extraction_rules_event_is_dict(mock_session, db_session):
    event = {"name": "Test Alert", "source": ["source_test"]}
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ name }}",
        regex="Test Alert",
        disabled=False,
        pre=False,  # Rule applies to dict type events
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Mocking chevron rendering
    with patch("chevron.render", return_value="Test Alert"):
        enriched_event = enrichment_bl.run_extraction_rules(event)

    assert (
        enriched_event["name"] == "Test Alert"
    )  # Ensuring the attribute is correctly processed


@pytest.mark.asyncio
def test_run_extraction_rules_no_rules(mock_session, mock_alert_dto, db_session):
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = (
        []
    )
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)
    result_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    assert (
        result_event == mock_alert_dto
    )  # Should return the original event if no rules apply


@pytest.mark.asyncio
def test_run_extraction_rules_attribute_no_template(mock_session, mock_alert_dto, db_session):
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="name",  # No {{}} in attribute
        regex="Test",
        disabled=False,
        pre=True,
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    with patch("chevron.render", return_value="Test Alert"):
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    assert (
        "name" not in enriched_event
    )  # Assuming the code does not modify the event if attribute is not in template format


@pytest.mark.asyncio
def test_run_extraction_rules_empty_attribute_value(mock_session, mock_alert_dto, db_session):
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ description }}",  # Assume description is empty
        regex=".*",
        disabled=False,
        pre=True,
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    with patch("chevron.render", return_value=""):
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    assert enriched_event == mock_alert_dto  # Check if event is unchanged


@pytest.mark.asyncio
def test_run_extraction_rules_handle_source_special_case(mock_session, db_session):
    event = {"name": "Test Alert", "source": "incorrect_format"}
    rule = ExtractionRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ source }}",
        regex="(?P<source>incorrect_format)",
        disabled=False,
        pre=True,
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # We'll mock chevron to return the exact content of 'source' to simulate the template rendering
    with patch("chevron.render", return_value="incorrect_format"):
        # We need to mock 're.search' to return a match object with a groupdict that includes 'source'
        with patch(
            "re.search",
            return_value=Mock(groupdict=lambda: {"source": "incorrect_format"}),
        ):
            enriched_event = enrichment_bl.run_extraction_rules(event)

    # Assert that the event's 'source' is now a list with the updated source
    assert enriched_event["source"] == [
        "incorrect_format"
    ], "Source should be updated to a list containing the new source."


#### 2. Testing `run_extraction_rules` with CEL Conditions


@pytest.mark.asyncio
def test_run_extraction_rules_with_conditions(mock_session, mock_alert_dto, db_session):
    rule = ExtractionRule(
        id=2,
        tenant_id="test_tenant",
        priority=1,
        attribute="{{ source[0] }}",
        regex="(?P<source_name>test_source)",
        disabled=False,
        pre=False,
        condition='source.includes("test_source")',
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    # Mocking the CEL environment to return True for the condition
    with patch("chevron.render", return_value="test_source"), patch(
        "celpy.Environment"
    ) as mock_env, patch("celpy.celpy.json_to_cel") as mock_json_to_cel:
        mock_env.return_value.compile.return_value = None
        mock_program = Mock()
        mock_env.return_value.program.return_value = mock_program
        mock_program.evaluate.return_value = True
        mock_json_to_cel.return_value = {}

        enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    # Assert that the event is now enriched with the source name from regex
    assert enriched_event.source_name == "test_source"


@pytest.mark.asyncio
def test_run_mapping_rules_applies(mock_session, mock_alert_dto, db_session):
    # Setup a mapping rule
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=["name"],
        rows=[{"name": "Test Alert", "service": "new_service"}],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    enrichment_bl.run_mapping_rules(mock_alert_dto)

    # Check if the alert's service is now updated to "new_service"
    assert mock_alert_dto.service == "new_service"


@pytest.mark.asyncio
def test_run_mapping_rules_with_regex_match(mock_session, mock_alert_dto, db_session):
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=["name"],
        rows=[
            {"name": "^(keep-)?backend-service$", "service": "backend_service"},
            {"name": "frontend-service", "service": "frontend_service"},
        ],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Test case where the alert name matches the regex pattern with 'keep-' prefix
    mock_alert_dto.name = "keep-backend-service"
    del mock_alert_dto.service
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert (
        mock_alert_dto.service == "backend_service"
    ), "Service should match 'backend_service' for 'keep-backend-service'"

    # Test case where the alert name matches the regex pattern without 'keep-' prefix
    mock_alert_dto.name = "backend-service"
    del mock_alert_dto.service
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert (
        mock_alert_dto.service == "backend_service"
    ), "Service should match 'backend_service' for 'backend-service'"

    # Test case where the alert name does not match any regex pattern
    mock_alert_dto.name = "unmatched-service"
    del mock_alert_dto.service
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert (
        hasattr(mock_alert_dto, "service") is False
    ), "Service should not match any entry"


@pytest.mark.asyncio
def test_run_mapping_rules_no_match(mock_session, mock_alert_dto, db_session):
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=["name"],
        rows=[
            {"name": "^(keep-)?backend-service$", "service": "backend_service"},
            {"name": "frontend-service", "service": "frontend_service"},
        ],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session
    del mock_alert_dto.service

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Test case where no entry matches the regex pattern
    mock_alert_dto.name = "unmatched-service"
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert (
        hasattr(mock_alert_dto, "service") is False
    ), "Service should not match any entry"


@pytest.mark.asyncio
def test_check_matcher_with_and_condition(mock_session, mock_alert_dto, db_session):
    # Setup a mapping rule with && condition in matchers
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=["name && severity"],
        rows=[{"name": "Test Alert", "severity": "high", "service": "new_service"}],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Test case where alert matches both name and severity conditions
    mock_alert_dto.name = "Test Alert"
    mock_alert_dto.severity = "high"
    matcher_exist = enrichment_bl._check_matcher(
        mock_alert_dto, rule.rows[0], "name && severity"
    )
    assert matcher_exist
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert mock_alert_dto.service == "new_service"
    del mock_alert_dto.service
    # Test case where alert does not match both conditions
    mock_alert_dto.name = "Other Alert"
    mock_alert_dto.severity = "low"
    result = enrichment_bl._check_matcher(
        mock_alert_dto, rule.rows[0], "name && severity"
    )
    assert not hasattr(mock_alert_dto, "service")
    assert result is False


@pytest.mark.asyncio
def test_check_matcher_with_or_condition(mock_session, mock_alert_dto, db_session):
    # Setup a mapping rule with || condition in matchers
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=["name", "severity"],
        rows=[
            {"name": "Test Alert", "service": "new_service"},
            {"severity": "high", "service": "high_severity_service"},
        ],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Test case where alert matches name condition
    mock_alert_dto.name = "Test Alert"
    del mock_alert_dto.service
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert mock_alert_dto.service == "new_service"

    # Test case where alert matches severity condition
    mock_alert_dto.name = "Other Alert"
    mock_alert_dto.severity = "high"
    del mock_alert_dto.service
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert mock_alert_dto.service == "high_severity_service"
    del mock_alert_dto.service
    # Test case where alert matches neither condition
    mock_alert_dto.name = "Other Alert"
    mock_alert_dto.severity = "low"
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert not hasattr(mock_alert_dto, "service")


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["sentry"], "severity": "critical"},
                {"source": ["grafana"], "severity": "critical"},
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.asyncio
async def test_mapping_rule_with_elsatic(mock_session, mock_alert_dto, setup_alerts, db_session):
    import os

    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    # Setup a mapping rule with || condition in matchers
    rule = MappingRule(
        id=1,
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        matchers=["name", "severity"],
        rows=[
            {"name": "Test Alert", "service": "new_service"},
            {"severity": "high", "service": "high_severity_service"},
        ],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=mock_session)

    # Test case where alert matches name condition
    mock_alert_dto.name = "Test Alert"
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert mock_alert_dto.service == "new_service"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.asyncio
def test_enrichment(db_session, client, test_app, mock_alert_dto, elastic_client):
    # add some rule
    rule = MappingRule(
        id=1,
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        matchers=["name", "severity"],
        rows=[
            {"name": "Test Alert", "service": "new_service"},
            {"severity": "high", "service": "high_severity_service"},
        ],
        name="new_rule",
        disabled=False,
        type="csv",
    )
    db_session.add(rule)
    db_session.commit()

    # now post an alert
    response = client.post(
        "/alerts/event",
        headers={"x-api-key": "some-key-everything-works-because-no-auth"},
        json=mock_alert_dto.dict(),
    )

    # now query the feed preset to get the alerts
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key-everything-works-because-no-auth"},
    )
    alerts = response.json()
    assert len(alerts) == 1
    assert response.headers.get("x-search-type") == "elastic"
    alert = alerts[0]
    assert alert["service"] == "new_service"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.asyncio
def test_disposable_enrichment(db_session, client, test_app, mock_alert_dto):
    # SHAHAR: there is a voodoo so that you must do something with the db_session to kick it off
    rule = MappingRule(
        id=1,
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        matchers=["name", "severity"],
        rows=[
            {"name": "Test Alert", "service": "new_service"},
            {"severity": "high", "service": "high_severity_service"},
        ],
        name="new_rule",
        disabled=False,
        type="csv",
    )
    db_session.add(rule)
    db_session.commit()
    # 1. send alert
    response = client.post(
        "/alerts/event",
        headers={"x-api-key": "some-key"},
        json=mock_alert_dto.dict(),
    )

    while (
        client.get(
            f"/alerts/{mock_alert_dto.fingerprint}",
            headers={"x-api-key": "some-key"},
        ).status_code
        != 200
    ):
        time.sleep(0.1)

    # 2. enrich with disposable alert
    response = client.post(
        "/alerts/enrich?dispose_on_new_alert=true",
        headers={"x-api-key": "some-key"},
        json={
            "fingerprint": mock_alert_dto.fingerprint,
            "enrichments": {
                "status": "acknowledged",
            },
        },
    )

    # 3. get the alert with the new status
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()
    while alerts[0]["status"] != "acknowledged":
        response = client.get(
            "/preset/feed/alerts",
            headers={"x-api-key": "some-key"},
        )
        alerts = response.json()

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["status"] == "acknowledged"

    # 4. send the alert again with firing and check that the status is reset
    mock_alert_dto.status = "firing"
    setattr(mock_alert_dto, "avoid_dedup", "bla")
    response = client.post(
        "/alerts/event",
        headers={"x-api-key": "some-key"},
        json=mock_alert_dto.dict(),
    )
    # 5. get the alert with the new status
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()
    while alerts[0]["status"] != "firing":
        time.sleep(0.1)
        response = client.get(
            "/preset/feed/alerts",
            headers={"x-api-key": "some-key"},
        )
        alerts = response.json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["status"] == "firing"


@pytest.mark.asyncio
def test_topology_mapping_rule_enrichment(mock_session, mock_alert_dto, db_session):
    # Mock a TopologyService with dependencies to simulate the DB structure
    mock_topology_service = TopologyService(
        id=1, tenant_id="keep", service="test-service", display_name="Test Service"
    )

    # Create a mock MappingRule for topology
    rule = MappingRule(
        id=3,
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        matchers=["service"],
        name="topology_rule",
        disabled=False,
        type="topology",
    )

    # Mock the session to return this topology mapping rule
    mock_session.query.return_value.filter.return_value.all.return_value = [rule]
    mock_session.db_session = db_session

    # Initialize the EnrichmentsBl class with the mock session
    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    mock_alert_dto.service = "test-service"

    # Mock the get_topology_data_by_dynamic_matcher to return the mock topology service
    with patch(
        "keep.api.bl.enrichments_bl.get_topology_data_by_dynamic_matcher",
        return_value=mock_topology_service,
    ):
        # Mock the enrichment database function so no actual DB actions occur
        with patch(
            "keep.api.bl.enrichments_bl.enrich_alert_db"
        ) as mock_enrich_alert_db:
            # Run the mapping rule logic for the topology
            result_event = enrichment_bl.run_mapping_rules(mock_alert_dto)

            # Check that the topology enrichment was applied correctly
            assert getattr(result_event, "display_name", None) == "Test Service"

            # Verify that the DB enrichment function was called correctly
            mock_enrich_alert_db.assert_called_once_with(
                "test_tenant",
                mock_alert_dto.fingerprint,
                {
                    "source_provider_id": "unknown",
                    "service": "test-service",
                    "environment": "unknown",
                    "display_name": "Test Service",
                },
                action_callee="system",
                action_type=AlertActionType.MAPPING_RULE_ENRICH,
                action_description="Alert enriched with mapping from rule `topology_rule`",
                session=mock_session,
                force=False,
                audit_enabled=True,
            )


@pytest.mark.asyncio
def test_run_mapping_rules_with_complex_matchers(mock_session, mock_alert_dto, db_session):
    # Setup a mapping rule with complex matchers
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=["name && severity", "source"],
        rows=[
            {
                "name": "Test Alert",
                "severity": "high",
                "service": "high_priority_service",
            },
            {
                "name": "Test Alert",
                "severity": "low",
                "service": "low_priority_service",
            },
            {"source": "test_source", "service": "source_specific_service"},
        ],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Test case 1: Matches "name && severity"
    mock_alert_dto.name = "Test Alert"
    mock_alert_dto.severity = "high"
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert mock_alert_dto.service == "high_priority_service"

    # Test case 2: Matches "name && severity" (different severity)
    mock_alert_dto.severity = "low"
    del mock_alert_dto.service
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert mock_alert_dto.service == "low_priority_service"

    # Test case 3: Matches "source"
    mock_alert_dto.name = "Different Alert"
    mock_alert_dto.severity = "medium"
    mock_alert_dto.source = ["test_source"]
    del mock_alert_dto.service
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert mock_alert_dto.service == "source_specific_service"

    # Test case 4: No match
    mock_alert_dto.name = "Unmatched Alert"
    mock_alert_dto.severity = "medium"
    mock_alert_dto.source = ["different_source"]
    del mock_alert_dto.service
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert not hasattr(mock_alert_dto, "service")


@pytest.mark.asyncio
def test_run_mapping_rules_enrichments_filtering(mock_session, mock_alert_dto, db_session):
    # Setup a mapping rule with complex matchers and multiple enrichment fields
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=["name && severity"],
        rows=[
            {
                "name": "Test Alert",
                "severity": "high",
                "service": "high_priority_service",
                "team": "on-call",
                "priority": "P1",
            },
        ],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]
    mock_session.db_session = db_session

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Test case: Matches "name && severity" and applies multiple enrichments
    mock_alert_dto.name = "Test Alert"
    mock_alert_dto.severity = "high"
    enrichment_bl.run_mapping_rules(mock_alert_dto)

    assert mock_alert_dto.service == "high_priority_service"
    assert mock_alert_dto.team == "on-call"
    assert mock_alert_dto.priority == "P1"
