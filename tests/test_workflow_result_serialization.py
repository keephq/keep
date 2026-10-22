import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from keep.api.core import db
from keep.api.models.alert import AlertDto


@pytest.fixture
def workflow_execution_session(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    execution = MagicMock()
    session.exec.return_value.one.return_value = execution
    monkeypatch.setattr(db, "Session", lambda engine: session)
    return session, execution


def test_save_workflow_results_encodes_alert_dtos_without_warning(
    workflow_execution_session, caplog
):
    session, execution = workflow_execution_session
    alert = AlertDto(
        name="slow-query",
        status="firing",
        severity="warning",
        lastReceived="2026-09-24T14:38:37Z",
        labels={"observed_at": datetime(2026, 9, 24, tzinfo=timezone.utc)},
    )

    with caplog.at_level(logging.WARNING, logger=db.__name__):
        db.save_workflow_results("tenant", "execution", {"sync-alerts": [alert]})

    assert execution.results["sync-alerts"][0]["name"] == "slow-query"
    assert execution.results["sync-alerts"][0]["labels"]["observed_at"] == (
        "2026-09-24T00:00:00+00:00"
    )
    json.dumps(execution.results)
    session.commit.assert_called_once()
    assert not caplog.records


def test_save_workflow_results_preserves_json_values(workflow_execution_session):
    session, execution = workflow_execution_session
    results = {"query": {"count": 3, "rows": [1, None, True]}}

    db.save_workflow_results("tenant", "execution", results)

    assert execution.results is results
    session.commit.assert_called_once()


def test_save_workflow_results_uses_legacy_fallback_for_unencodable_values(
    workflow_execution_session, caplog
):
    session, execution = workflow_execution_session

    with caplog.at_level(logging.WARNING, logger=db.__name__):
        db.save_workflow_results("tenant", "execution", {"bad": object()})

    assert isinstance(execution.results["bad"], str)
    session.commit.assert_called_once()
    assert len(caplog.records) == 1
    assert "legacy serializer" in caplog.records[0].message
