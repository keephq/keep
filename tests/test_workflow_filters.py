from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto
from keep.api.models.db.workflow import Workflow as WorkflowDB
from keep.workflowmanager.workflowmanager import WorkflowManager


def test_regex_service_filter(db_session):
    """Test regex pattern matching for service name"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: service-check
triggers:
- type: alert
  filters:
  - key: service
    value: r"(payments|ftp)"
"""
    workflow = WorkflowDB(
        id="service-check",
        name="service-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle alerts for specific services",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match
    payments_alert = AlertDto(
        id="alert-1",
        source=["grafana"],
        name="error-alert",
        service="payments",
        status="firing",
        severity="critical",
        fingerprint="fp1",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    ftp_alert = AlertDto(
        id="alert-2",
        source=["grafana"],
        name="error-alert",
        service="ftp",
        status="firing",
        severity="critical",
        fingerprint="fp2",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    # Should not match
    other_alert = AlertDto(
        id="alert-3",
        source=["grafana"],
        name="error-alert",
        service="email",
        status="firing",
        severity="critical",
        fingerprint="fp3",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [payments_alert, ftp_alert, other_alert]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 2

    # Validate specific alerts in workflows_to_run
    triggered_alerts = [
        w.get("event") for w in workflow_manager.scheduler.workflows_to_run
    ]
    assert any(a.id == "alert-1" and a.service == "payments" for a in triggered_alerts)
    assert any(a.id == "alert-2" and a.service == "ftp" for a in triggered_alerts)


def test_multiple_source_regex(db_session):
    """Test regex pattern matching for multiple sources"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: source-check
triggers:
- type: alert
  filters:
  - key: source
    value: r"(grafana|prometheus)"
"""
    workflow = WorkflowDB(
        id="source-check",
        name="source-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle alerts from multiple sources",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    grafana_alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="alert1",
        status="firing",
        severity="critical",
        fingerprint="fp1",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    prometheus_alert = AlertDto(
        id="prom-1",
        source=["prometheus"],
        name="alert2",
        status="firing",
        severity="warning",
        fingerprint="fp2",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    sentry_alert = AlertDto(
        id="sentry-1",
        source=["sentry"],
        name="alert3",
        status="firing",
        severity="error",
        fingerprint="fp3",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [grafana_alert, prometheus_alert, sentry_alert]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 2

    # Validate triggered alerts
    triggered_alerts = [
        w.get("event") for w in workflow_manager.scheduler.workflows_to_run
    ]
    assert any(
        a.id == "grafana-1" and a.source == ["grafana"] for a in triggered_alerts
    )
    assert any(
        a.id == "prom-1" and a.source == ["prometheus"] for a in triggered_alerts
    )
    assert not any(a.id == "sentry-1" for a in triggered_alerts)


def test_combined_filters_with_regex(db_session):
    """Test combination of regex and exact match filters"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: combined-check
triggers:
- type: alert
  filters:
  - key: source
    value: sentry
  - key: severity
    value: critical
  - key: service
    value: r"(payments|ftp)"
"""
    workflow = WorkflowDB(
        id="combined-check",
        name="combined-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle specific alerts with combined conditions",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match
    matching_alert = AlertDto(
        id="sentry-1",
        source=["sentry"],
        name="error",
        service="payments",
        status="firing",
        severity="critical",
        fingerprint="fp1",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    # Wrong severity
    wrong_severity = AlertDto(
        id="sentry-2",
        source=["sentry"],
        name="error",
        service="payments",
        status="firing",
        severity="warning",
        fingerprint="fp2",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    workflow_manager.insert_events(SINGLE_TENANT_UUID, [matching_alert, wrong_severity])
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    # Validate the triggered alert
    triggered_alert = workflow_manager.scheduler.workflows_to_run[0].get("event")
    assert triggered_alert.id == "sentry-1"
    assert triggered_alert.source == ["sentry"]
    assert triggered_alert.severity == "critical"
    assert triggered_alert.service == "payments"


def test_wildcard_source_filter(db_session):
    """Test wildcard regex pattern for source"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: wildcard-check
triggers:
- type: alert
  filters:
  - key: source
    value: r".*"
"""
    workflow = WorkflowDB(
        id="wildcard-check",
        name="wildcard-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle all alerts regardless of source",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    test_sources = ["grafana", "prometheus", "sentry", "custom"]
    alerts = [
        AlertDto(
            id=f"alert-{i}",
            source=[source],
            name="test-alert",
            status="firing",
            severity="critical",
            fingerprint=f"fp{i}",
            lastReceived="2025-01-30T09:19:02.519Z",
        )
        for i, source in enumerate(test_sources)
    ]

    workflow_manager.insert_events(SINGLE_TENANT_UUID, alerts)
    assert len(workflow_manager.scheduler.workflows_to_run) == 4

    # Validate all alerts are triggered
    triggered_alerts = [
        w.get("event") for w in workflow_manager.scheduler.workflows_to_run
    ]
    for i, source in enumerate(test_sources):
        assert any(
            a.id == f"alert-{i}"
            and a.source == [source]
            and a.lastReceived == "2025-01-30T09:19:02.519Z"
            for a in triggered_alerts
        )


def test_multiple_filters_with_exclusion(db_session):
    """Test multiple filters including exclusion"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: complex-check
triggers:
- type: alert
  filters:
  - key: source
    value: r"(grafana|prometheus)"
  - key: severity
    value: critical
  - key: service
    value: database
    exclude: true
"""
    workflow = WorkflowDB(
        id="complex-check",
        name="complex-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Complex filter combination",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match
    matching_alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="error",
        service="api",
        status="firing",
        severity="critical",
        fingerprint="fp1",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    # Excluded service
    excluded_alert = AlertDto(
        id="prometheus-1",
        source=["prometheus"],
        name="error",
        service="database",
        status="firing",
        severity="critical",
        fingerprint="fp2",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    workflow_manager.insert_events(SINGLE_TENANT_UUID, [matching_alert, excluded_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    # Validate the triggered alert
    triggered_alert = workflow_manager.scheduler.workflows_to_run[0].get("event")
    assert triggered_alert.id == "grafana-1"
    assert triggered_alert.source == ["grafana"]
    assert triggered_alert.service == "api"
    assert triggered_alert.severity == "critical"
    assert triggered_alert.lastReceived == "2025-01-30T09:19:02.519Z"


def test_nested_regex_patterns(db_session):
    """Test nested regex patterns with special characters"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: nested-regex
triggers:
- type: alert
  filters:
  - key: name
    value: r"error\\.[a-z]+\\.(critical|warning)"
"""
    workflow = WorkflowDB(
        id="nested-regex",
        name="nested-regex",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle nested error patterns",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match
    matching_alerts = [
        AlertDto(
            id="alert-1",
            source=["grafana"],
            name="error.database.critical",
            status="firing",
            severity="critical",
            fingerprint="fp1",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
        AlertDto(
            id="alert-2",
            source=["grafana"],
            name="error.api.warning",
            status="firing",
            severity="warning",
            fingerprint="fp2",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
    ]

    # Should not match
    non_matching_alerts = [
        AlertDto(
            id="alert-3",
            source=["grafana"],
            name="error.network.info",
            status="firing",
            severity="info",
            fingerprint="fp3",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
        AlertDto(
            id="alert-4",
            source=["grafana"],
            name="warning.system.critical",
            status="firing",
            severity="critical",
            fingerprint="fp4",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
    ]

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, matching_alerts + non_matching_alerts
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 2

    triggered_alerts = [
        w.get("event") for w in workflow_manager.scheduler.workflows_to_run
    ]
    assert any(
        a.id == "alert-1" and a.name == "error.database.critical"
        for a in triggered_alerts
    )
    assert any(
        a.id == "alert-2" and a.name == "error.api.warning" for a in triggered_alerts
    )


def test_time_based_filters(db_session):
    """Test filtering alerts based on lastReceived timestamp patterns"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: time-check
triggers:
- type: alert
  filters:
  - key: lastReceived
    value: r"2025-01-30T09:.*"
  - key: severity
    value: critical
"""
    workflow = WorkflowDB(
        id="time-check",
        name="time-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle time-sensitive alerts",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match (correct time pattern and severity)
    matching_alert = AlertDto(
        id="alert-1",
        source=["grafana"],
        name="error-alert",
        status="firing",
        severity="critical",
        fingerprint="fp1",
        lastReceived="2025-01-30T09:15:00.000Z",
    )

    # Wrong time pattern
    wrong_time = AlertDto(
        id="alert-2",
        source=["grafana"],
        name="error-alert",
        status="firing",
        severity="critical",
        fingerprint="fp2",
        lastReceived="2025-01-30T10:19:02.519Z",
    )

    # Wrong severity
    wrong_severity = AlertDto(
        id="alert-3",
        source=["grafana"],
        name="error-alert",
        status="firing",
        severity="warning",
        fingerprint="fp3",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [matching_alert, wrong_time, wrong_severity]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    triggered_alert = workflow_manager.scheduler.workflows_to_run[0].get("event")
    assert triggered_alert.id == "alert-1"
    assert triggered_alert.severity == "critical"
    assert triggered_alert.lastReceived.startswith("2025-01-30T09:")


def test_empty_string_filters(db_session):
    """Test handling of empty string values in filters"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: empty-check
triggers:
- type: alert
  filters:
  - key: service
    value: r"^$"
  - key: severity
    value: critical
"""
    workflow = WorkflowDB(
        id="empty-check",
        name="empty-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle alerts with empty fields",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match (empty service field)
    matching_alert = AlertDto(
        id="alert-1",
        source=["grafana"],
        name="error-alert",
        service="",
        status="firing",
        severity="critical",
        fingerprint="fp1",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    # Non-empty service field
    non_empty_service = AlertDto(
        id="alert-2",
        source=["grafana"],
        name="error-alert",
        service="api",
        status="firing",
        severity="critical",
        fingerprint="fp2",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [matching_alert, non_empty_service]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    triggered_alert = workflow_manager.scheduler.workflows_to_run[0].get("event")
    assert triggered_alert.id == "alert-1"
    assert triggered_alert.service == ""
    assert triggered_alert.severity == "critical"


def test_nested_regex_patterns(db_session):
    """Test nested regex patterns with special characters"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: nested-regex
triggers:
- type: alert
  filters:
  - key: name
    value: r"error\\.[a-z]+\\.(critical|warning)"
"""
    workflow = WorkflowDB(
        id="nested-regex",
        name="nested-regex",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle nested error patterns",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match
    matching_alerts = [
        AlertDto(
            id="alert-1",
            source=["grafana"],
            name="error.database.critical",
            status="firing",
            severity="critical",
            fingerprint="fp1",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
        AlertDto(
            id="alert-2",
            source=["grafana"],
            name="error.api.warning",
            status="firing",
            severity="warning",
            fingerprint="fp2",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
    ]

    # Should not match
    non_matching_alerts = [
        AlertDto(
            id="alert-3",
            source=["grafana"],
            name="error.network.info",
            status="firing",
            severity="info",
            fingerprint="fp3",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
        AlertDto(
            id="alert-4",
            source=["grafana"],
            name="warning.system.critical",
            status="firing",
            severity="critical",
            fingerprint="fp4",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
    ]

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, matching_alerts + non_matching_alerts
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 2

    triggered_alerts = [
        w.get("event") for w in workflow_manager.scheduler.workflows_to_run
    ]
    assert any(
        a.id == "alert-1" and a.name == "error.database.critical"
        for a in triggered_alerts
    )
    assert any(
        a.id == "alert-2" and a.name == "error.api.warning" for a in triggered_alerts
    )


def test_time_based_filters(db_session):
    """Test filtering alerts based on lastReceived timestamp patterns"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: time-check
triggers:
- type: alert
  filters:
  - key: lastReceived
    value: r"2025-01-30T09:.*"
  - key: severity
    value: critical
"""
    workflow = WorkflowDB(
        id="time-check",
        name="time-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle time-sensitive alerts",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match (correct time pattern and severity)
    matching_alert = AlertDto(
        id="alert-1",
        source=["grafana"],
        name="error-alert",
        status="firing",
        severity="critical",
        fingerprint="fp1",
        lastReceived="2025-01-30T09:15:00.000Z",
    )

    # Wrong time pattern
    wrong_time = AlertDto(
        id="alert-2",
        source=["grafana"],
        name="error-alert",
        status="firing",
        severity="critical",
        fingerprint="fp2",
        lastReceived="2025-01-30T10:19:02.519Z",
    )

    # Wrong severity
    wrong_severity = AlertDto(
        id="alert-3",
        source=["grafana"],
        name="error-alert",
        status="firing",
        severity="warning",
        fingerprint="fp3",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [matching_alert, wrong_time, wrong_severity]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    triggered_alert = workflow_manager.scheduler.workflows_to_run[0].get("event")
    assert triggered_alert.id == "alert-1"
    assert triggered_alert.severity == "critical"
    assert triggered_alert.lastReceived.startswith("2025-01-30T09:")


def test_empty_string_filters(db_session):
    """Test handling of empty string values in filters"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: empty-check
triggers:
- type: alert
  filters:
  - key: service
    value: r"^$"
  - key: severity
    value: critical
"""
    workflow = WorkflowDB(
        id="empty-check",
        name="empty-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle alerts with empty fields",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match (empty service field)
    matching_alert = AlertDto(
        id="alert-1",
        source=["grafana"],
        name="error-alert",
        service="",
        status="firing",
        severity="critical",
        fingerprint="fp1",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    # Non-empty service field
    non_empty_service = AlertDto(
        id="alert-2",
        source=["grafana"],
        name="error-alert",
        service="api",
        status="firing",
        severity="critical",
        fingerprint="fp2",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [matching_alert, non_empty_service]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    triggered_alert = workflow_manager.scheduler.workflows_to_run[0].get("event")
    assert triggered_alert.id == "alert-1"
    assert triggered_alert.service == ""
    assert triggered_alert.severity == "critical"


def test_multiple_exclusion_filters(db_session):
    """Test multiple exclusion filters in combination"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: multi-exclude
triggers:
- type: alert
  filters:
  - key: service
    value: r"(api|database|cache)"
  - key: severity
    value: r"(critical|warning)"
    exclude: true
  - key: status
    value: resolved
    exclude: true
"""
    workflow = WorkflowDB(
        id="multi-exclude",
        name="multi-exclude",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle alerts with multiple exclusions",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match (info severity, firing status)
    matching_alert = AlertDto(
        id="alert-1",
        source=["grafana"],
        name="error-alert",
        service="api",
        status="firing",
        severity="info",
        fingerprint="fp1",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    # Should not match (excluded severity)
    excluded_severity = AlertDto(
        id="alert-2",
        source=["grafana"],
        name="error-alert",
        service="database",
        status="firing",
        severity="warning",
        fingerprint="fp2",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    # Should not match (excluded status)
    excluded_status = AlertDto(
        id="alert-3",
        source=["grafana"],
        name="error-alert",
        service="cache",
        status="resolved",
        severity="info",
        fingerprint="fp3",
        lastReceived="2025-01-30T09:19:02.519Z",
    )

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [matching_alert, excluded_severity, excluded_status]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    triggered_alert = workflow_manager.scheduler.workflows_to_run[0].get("event")
    assert triggered_alert.id == "alert-1"
    assert triggered_alert.service == "api"
    assert triggered_alert.severity == "info"
    assert triggered_alert.status == "firing"


def test_regex_exclusion_patterns(db_session):
    """Test regex patterns with exclusion"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: regex-exclude
triggers:
- type: alert
  filters:
  - key: name
    value: r"error\\.[a-z]+\\..*"
  - key: name
    value: r"error\\.database\\..*"
    exclude: true
"""
    workflow = WorkflowDB(
        id="regex-exclude",
        name="regex-exclude",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle alerts with regex exclusions",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match
    matching_alerts = [
        AlertDto(
            id="alert-1",
            source=["grafana"],
            name="error.api.critical",
            status="firing",
            severity="critical",
            fingerprint="fp1",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
        AlertDto(
            id="alert-2",
            source=["grafana"],
            name="error.cache.warning",
            status="firing",
            severity="warning",
            fingerprint="fp2",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
    ]

    # Should not match (excluded pattern)
    excluded_alerts = [
        AlertDto(
            id="alert-3",
            source=["grafana"],
            name="error.database.critical",
            status="firing",
            severity="critical",
            fingerprint="fp3",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
        AlertDto(
            id="alert-4",
            source=["grafana"],
            name="error.database.warning",
            status="firing",
            severity="warning",
            fingerprint="fp4",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
    ]

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, matching_alerts + excluded_alerts
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 2

    triggered_alerts = [
        w.get("event") for w in workflow_manager.scheduler.workflows_to_run
    ]
    assert any(a.id == "alert-1" and "database" not in a.name for a in triggered_alerts)
    assert any(a.id == "alert-2" and "database" not in a.name for a in triggered_alerts)


def test_exclusion_with_source_list(db_session):
    """Test exclusion filters with source list values"""
    workflow_manager = WorkflowManager()
    workflow_definition = """workflow:
id: source-exclude
triggers:
- type: alert
  filters:
  - key: source
    value: r".*"
  - key: source
    value: r"(prometheus|sentry)"
    exclude: true
  - key: severity
    value: critical
"""
    workflow = WorkflowDB(
        id="source-exclude",
        name="source-exclude",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle alerts with source exclusions",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    # Should match
    matching_alerts = [
        AlertDto(
            id="alert-1",
            source=["grafana"],
            name="error-alert",
            status="firing",
            severity="critical",
            fingerprint="fp1",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
        AlertDto(
            id="alert-2",
            source=["custom"],
            name="error-alert",
            status="firing",
            severity="critical",
            fingerprint="fp2",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
    ]

    # Should not match (excluded sources)
    excluded_alerts = [
        AlertDto(
            id="alert-3",
            source=["prometheus"],
            name="error-alert",
            status="firing",
            severity="critical",
            fingerprint="fp3",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
        AlertDto(
            id="alert-4",
            source=["sentry"],
            name="error-alert",
            status="firing",
            severity="critical",
            fingerprint="fp4",
            lastReceived="2025-01-30T09:19:02.519Z",
        ),
    ]

    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, matching_alerts + excluded_alerts
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 2

    triggered_alerts = [
        w.get("event") for w in workflow_manager.scheduler.workflows_to_run
    ]
    assert any(a.id == "alert-1" and a.source == ["grafana"] for a in triggered_alerts)
    assert any(a.id == "alert-2" and a.source == ["custom"] for a in triggered_alerts)
