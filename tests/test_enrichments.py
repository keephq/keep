# test_enrichments.py
import time
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch
import uuid

import pytest
from sqlalchemy import text
from tenacity import sleep

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Alert
from keep.api.models.db.extraction import ExtractionRule
from keep.api.models.db.mapping import MappingRule
from keep.api.models.db.topology import TopologyService
from keep.api.models.db.workflow import Workflow
from keep.workflowmanager.workflowmanager import WorkflowManager
from tests.fixtures.client import client, setup_api_key, test_app
from tests.fixtures.workflow_manager import (
    wait_for_workflow_execution,
    wait_for_workflow_in_run_queue,
)  # noqa


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


def test_run_extraction_rules_no_rules_applies(mock_session, mock_alert_dto):
    # Assuming there are no extraction rules
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = (
        []
    )

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)
    result_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    # Check that the event has not changed (no rules to apply)
    assert result_event == mock_alert_dto  # Assuming no change if no rules


def test_run_extraction_rules_regex_named_groups(mock_session, mock_alert_dto):
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

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Mocking chevron rendering to simulate template rendering
    with patch("chevron.render", return_value="Test Alert"):
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    # Assert that the event is now enriched with regex group names
    assert enriched_event.service_name == "Test"
    assert enriched_event.alert_type == "Alert"


def test_run_extraction_rules_event_is_dict(mock_session):
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

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Mocking chevron rendering
    with patch("chevron.render", return_value="Test Alert"):
        enriched_event = enrichment_bl.run_extraction_rules(event)

    assert (
        enriched_event["name"] == "Test Alert"
    )  # Ensuring the attribute is correctly processed


def test_run_extraction_rules_no_rules(mock_session, mock_alert_dto):
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = (
        []
    )

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)
    result_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    assert (
        result_event == mock_alert_dto
    )  # Should return the original event if no rules apply


def test_run_extraction_rules_attribute_no_template(mock_session, mock_alert_dto):
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

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    with patch("chevron.render", return_value="Test Alert"):
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    assert (
        "name" not in enriched_event
    )  # Assuming the code does not modify the event if attribute is not in template format


def test_run_extraction_rules_empty_attribute_value(mock_session, mock_alert_dto):
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

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    with patch("chevron.render", return_value=""):
        enriched_event = enrichment_bl.run_extraction_rules(mock_alert_dto)

    assert enriched_event == mock_alert_dto  # Check if event is unchanged


#### 2. Testing `run_extraction_rules` with CEL Conditions


def test_run_extraction_rules_with_conditions(mock_session, mock_alert_dto):
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


def test_run_mapping_rules_applies(mock_session, mock_alert_dto):
    # Setup a mapping rule
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=[["name"]],
        rows=[{"name": "Test Alert", "service": "new_service"}],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    enrichment_bl.run_mapping_rules(mock_alert_dto)

    # Check if the alert's service is now updated to "new_service"
    assert mock_alert_dto.service == "new_service"


def test_run_mapping_rules_with_regex_match(mock_session, mock_alert_dto):
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=[["name"]],
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


def test_run_mapping_rules_no_match(mock_session, mock_alert_dto):
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=[["name"]],
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
    del mock_alert_dto.service

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Test case where no entry matches the regex pattern
    mock_alert_dto.name = "unmatched-service"
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert (
        hasattr(mock_alert_dto, "service") is False
    ), "Service should not match any entry"


def test_check_matcher_with_and_condition(mock_session, mock_alert_dto):
    # Setup a mapping rule with && condition in matchers
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=[["name", "severity"]],
        rows=[{"name": "Test Alert", "severity": "high", "service": "new_service"}],
        disabled=False,
        type="csv",
    )
    mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
        rule
    ]

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Test case where alert matches both name and severity conditions
    mock_alert_dto.name = "Test Alert"
    mock_alert_dto.severity = "high"
    matcher_exist = enrichment_bl._check_matcher(
        mock_alert_dto, rule.rows[0], ["name", "severity"]
    )
    assert matcher_exist
    enrichment_bl.run_mapping_rules(mock_alert_dto)
    assert mock_alert_dto.service == "new_service"
    del mock_alert_dto.service
    # Test case where alert does not match both conditions
    mock_alert_dto.name = "Other Alert"
    mock_alert_dto.severity = "low"
    result = enrichment_bl._check_matcher(
        mock_alert_dto, rule.rows[0], ["name", "severity"]
    )
    assert not hasattr(mock_alert_dto, "service")
    assert result is False


def test_check_matcher_with_or_condition(mock_session, mock_alert_dto):
    # Setup a mapping rule with || condition in matchers
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=[["name"], ["severity"]],
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
def test_mapping_rule_with_elastic(mock_session, mock_alert_dto, setup_alerts):
    import os

    # first, use elastic
    with patch.dict(os.environ, {"ELASTIC_ENABLED": "true"}):
        # Setup a mapping rule with || condition in matchers
        rule = MappingRule(
            id=1,
            tenant_id=SINGLE_TENANT_UUID,
            priority=1,
            matchers=[["name"], ["severity"]],
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

        enrichment_bl = EnrichmentsBl(tenant_id=SINGLE_TENANT_UUID, db=mock_session)

        # Test case where alert matches name condition
        mock_alert_dto.name = "Test Alert"
        enrichment_bl.run_mapping_rules(mock_alert_dto)
        assert mock_alert_dto.service == "new_service"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_enrichment_with_elastic(
    db_session, client, test_app, mock_alert_dto, elastic_client
):
    # add some rule
    rule = MappingRule(
        id=1,
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        matchers=[["name"], ["severity"]],
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

    # wait for the alert to be indexed
    sleep(1)

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
def test_enrichment(db_session, client, test_app, mock_alert_dto):
    # add some rule
    rule = MappingRule(
        id=1,
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        matchers=[["name"], ["severity"]],
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
    sleep(1)

    # now query the feed preset to get the alerts
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key-everything-works-because-no-auth"},
    )
    alerts = response.json()
    assert len(alerts) == 1
    assert response.headers.get("x-search-type") == "internal"
    alert = alerts[0]
    assert alert["service"] == "new_service"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
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


def test_topology_mapping_rule_enrichment(mock_session, mock_alert_dto):
    # Mock a TopologyService with dependencies to simulate the DB structure
    mock_topology_service = TopologyService(
        id=1, tenant_id="keep", service="test-service", display_name="Test Service"
    )

    # Create a mock MappingRule for topology
    rule = MappingRule(
        id=3,
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        matchers=[["service"]],
        name="topology_rule",
        disabled=False,
        type="topology",
    )

    # Mock the session to return this topology mapping rule
    mock_session.query.return_value.filter.return_value.all.return_value = [rule]

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
                    "is_manual": False,
                },
                action_callee="system",
                action_type=ActionType.MAPPING_RULE_ENRICH,
                action_description="Alert enriched with mapping from rule `topology_rule`",
                session=mock_session,
                force=False,
                audit_enabled=True,
            )


def test_run_mapping_rules_with_complex_matchers(mock_session, mock_alert_dto):
    # Setup a mapping rule with complex matchers
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=[["name", "severity"], ["source"]],
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


def test_run_mapping_rules_enrichments_filtering(mock_session, mock_alert_dto):
    # Setup a mapping rule with complex matchers and multiple enrichment fields
    rule = MappingRule(
        id=1,
        tenant_id="test_tenant",
        priority=1,
        matchers=[["name", "severity"]],
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

    enrichment_bl = EnrichmentsBl(tenant_id="test_tenant", db=mock_session)

    # Test case: Matches "name && severity" and applies multiple enrichments
    mock_alert_dto.name = "Test Alert"
    mock_alert_dto.severity = "high"
    enrichment_bl.run_mapping_rules(mock_alert_dto)

    assert mock_alert_dto.service == "high_priority_service"
    assert mock_alert_dto.team == "on-call"
    assert mock_alert_dto.priority == "P1"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_disposable_enrichment_and_alert_history(
    db_session, client, test_app, mock_alert_dto
):
    """
    Test instance-level enrichment with disposal and verify the alert-history endpoint.
    """

    # STEP 1: Add a mapping rule to the database for enrichment
    rule = MappingRule(
        id=1,
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        matchers=[["name"], ["severity"]],
        rows=[
            {"name": "Test Alert", "service": "new_service"},
            {"severity": "high", "service": "high_severity_service"},
        ],
        name="disposal_rule",
        disabled=False,
        type="csv",
    )
    db_session.add(rule)
    db_session.commit()

    # STEP 2: Send a new alert event
    response = client.post(
        "/alerts/event",
        headers={"x-api-key": "some-key"},
        json=mock_alert_dto.dict(),
    )
    assert response.status_code == 202

    while (
        client.get(
            f"/alerts/{mock_alert_dto.fingerprint}", headers={"x-api-key": "some-key"}
        ).status_code
        != 200
    ):
        time.sleep(0.1)

    # STEP 3: Send a disposable enrichment to the alert
    disposable_enrichment = {
        "fingerprint": mock_alert_dto.fingerprint,
        "enrichments": {"status": "acknowledged"},
    }
    response = client.post(
        "/alerts/enrich?dispose_on_new_alert=true",
        headers={"x-api-key": "some-key"},
        json=disposable_enrichment,
    )
    assert response.status_code == 200

    # STEP 4: Verify the alert reflects the disposable enrichment
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["status"] == "acknowledged", "Disposable enrichment not applied"

    # STEP 5: Send a new alert with the same fingerprint and ensure enrichment is reset
    mock_alert_dto.status = "firing"  # Reset status to firing
    setattr(mock_alert_dto, "avoid_dedup", "test-value")  # Ensure no deduplication
    response = client.post(
        "/alerts/event",
        headers={"x-api-key": "some-key"},
        json=mock_alert_dto.dict(),
    )
    assert response.status_code == 202

    # 1 enrichment for fingerprint + 1 for alert.id
    assert (
        db_session.execute(text("SELECT count(1) from alertenrichment")).scalar() == 2
    )

    # Verify the disposable enrichment is reset
    time.sleep(1)
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["status"] == "firing", "Disposable enrichment was not reset"

    # STEP 6: Validate alert history reflects known changes
    response = client.get(
        f"/alerts/{mock_alert_dto.fingerprint}/history",
        headers={"x-api-key": "some-key"},
    )
    assert response.status_code == 200
    history_entries = response.json()
    assert len(history_entries) >= 2, "History does not record all changes"

    # Verify the history reflects status transitions
    statuses = [entry["status"] for entry in history_entries]
    assert "acknowledged" in statuses, "Acknowledged state missing in history"
    assert "firing" in statuses, "Firing state missing in history"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.parametrize("elastic_client", [False, True], indirect=True)
def test_batch_enrichment(db_session, client, test_app, create_alert, elastic_client):
    for i in range(10):
        create_alert(
            f"alert-test-{i}",
            AlertStatus.FIRING,
            datetime.utcnow(),
            {},
        )

    alerts = db_session.query(Alert).all()

    fingerprints = [a.fingerprint for a in alerts]

    response = client.post(
        "/alerts/batch_enrich",
        headers={"x-api-key": "some-key"},
        json={
            "fingerprints": fingerprints,
            "enrichments": {
                "status": "acknowledged",
            },
        },
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "ok"

    time.sleep(1)

    # 3. get the alert with the new status
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    assert len(alerts) == 10
    assert [a["status"] for a in alerts] == ["acknowledged"] * 10


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_incident_manual_enrichment_integration(db_session, client, test_app):
    """
    Test scenario 1: Create incident via API → enrich it manually → fetch and check enrichment
    """
    # Create incident via API
    incident_payload = {
        "user_generated_name": "Test Incident for Manual Enrichment",
        "user_summary": "Test incident for manual enrichment integration test",
        "severity": "critical",
        "status": "firing",
    }

    # Create the incident
    response = client.post(
        "/incidents",
        headers={"x-api-key": "some-key"},
        json=incident_payload,
    )
    assert response.status_code == 202
    incident_data = response.json()
    incident_id = incident_data["id"]

    # Enrich the incident manually with jira_ticket field
    enrichment_payload = {"enrichments": {"jira_ticket": "12345"}}

    response = client.post(
        f"/incidents/{incident_id}/enrich",
        headers={"x-api-key": "some-key"},
        json=enrichment_payload,
    )
    assert response.status_code == 202

    # Fetch the incident and check the enrichment is there
    response = client.get(
        f"/incidents/{incident_id}",
        headers={"x-api-key": "some-key"},
    )
    assert response.status_code == 200
    incident_data = response.json()

    # Verify the enrichment was applied
    assert "enrichments" in incident_data
    assert incident_data["enrichments"]["jira_ticket"] == "12345"


@pytest.mark.parametrize(
    "test_app, db_session",
    [
        ("NO_AUTH", None),
        ("NO_AUTH", {"db": "mysql"}),
    ],
    indirect=True,
)
def test_incident_workflow_enrichment_integration(db_session, client, test_app):
    """
    Test scenario 2: Create workflow that enriches incidents → create incident → fetch and check enrichment
    """

    # Create a workflow that enriches every incident with jira_ticket field
    workflow_definition = """workflow:
  id: incident-jira-enricher-test
  name: Incident JIRA Enricher Test
  description: Test workflow that enriches incidents with JIRA ticket
  disabled: false
  triggers:
    - type: incident
      events:
        - created
  actions:
    - name: enrich-with-jira
      provider:
        type: console
        with:
          message: "Enriching incident {{ incident.user_generated_name }} with JIRA ticket"
          enrich_incident:
            - key: jira_ticket
              value: "12345"
"""

    # Add the workflow to the database
    workflow = Workflow(
        id="incident-jira-enricher-test",
        name="Incident JIRA Enricher Test",
        tenant_id=SINGLE_TENANT_UUID,
        description="Test workflow that enriches incidents with JIRA ticket",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
        last_updated=datetime.utcnow(),
    )
    db_session.add(workflow)
    db_session.commit()

    # Create incident via API
    incident_payload = {
        "user_generated_name": "Test Incident for Workflow Enrichment",
        "user_summary": "Test incident for workflow enrichment integration test",
        "severity": "critical",
        "status": "firing",
    }

    response = client.post(
        "/incidents",
        headers={"x-api-key": "some-key"},
        json=incident_payload,
    )
    assert response.status_code == 202
    incident_data = response.json()
    incident_id = incident_data["id"]

    # wait a bit, to be sure workflow is added to the queue
    assert wait_for_workflow_in_run_queue("incident-jira-enricher-test")

    # Wait for workflow execution to complete
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "incident-jira-enricher-test"
    )

    # Verify workflow execution was successful
    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    # Fetch the incident and check the enrichment is there
    response = client.get(
        f"/incidents/{incident_id}",
        headers={"x-api-key": "some-key"},
    )
    assert response.status_code == 200
    incident_data = response.json()

    # Verify the enrichment was applied by the workflow
    assert "enrichments" in incident_data
    assert incident_data["enrichments"]["jira_ticket"] == "12345"


@pytest.mark.parametrize(
    "test_app, db_session",
    [
        ("NO_AUTH", None),
        ("NO_AUTH", {"db": "mysql"}),
    ],
    indirect=True,
)
def test_alert_enrichment_via_api_uuid(db_session, client, test_app, create_alert):
    fingerprint = str(uuid.uuid4())

    create_alert(
        fingerprint,
        AlertStatus.FIRING,
        datetime.utcnow(),
        {},
    )

    enrichment_response = client.post(
        "/alerts/enrich",
        headers={"x-api-key": "some-key"},
        json={
            "fingerprint": fingerprint,
            "enrichments": {
                "jira_ticket": "12345",
            },
        },
    )

    assert enrichment_response.status_code == 200

    alert_response = client.get(
        f"/alerts/{fingerprint}",
        headers={"x-api-key": "some-key"},
    )
    assert alert_response.status_code == 200
    alert_data = alert_response.json()

    assert alert_data["enriched_fields"] == ["jira_ticket"]
    assert alert_data["jira_ticket"] == "12345"


@pytest.mark.parametrize(
    "test_app, db_session",
    [
        ("NO_AUTH", None),
        ("NO_AUTH", {"db": "mysql"}),
    ],
    indirect=True,
)
def test_alert_enrichment_via_api_non_uuid(db_session, client, test_app, create_alert):
    not_uuid_fingerprint = "not-uuid-fingerprint"

    create_alert(
        not_uuid_fingerprint,
        AlertStatus.FIRING,
        datetime.utcnow(),
        {},
    )

    enrichment_response = client.post(
        "/alerts/enrich",
        headers={"x-api-key": "some-key"},
        json={
            "fingerprint": "not-uuid-fingerprint",
            "enrichments": {
                "jira_ticket": "12345",
            },
        },
    )

    assert enrichment_response.status_code == 200

    alert_response = client.get(
        f"/alerts/{not_uuid_fingerprint}",
        headers={"x-api-key": "some-key"},
    )
    assert alert_response.status_code == 200
    alert_data = alert_response.json()

    assert alert_data["enriched_fields"] == ["jira_ticket"]
    assert alert_data["jira_ticket"] == "12345"
