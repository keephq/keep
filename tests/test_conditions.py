import io
import logging
import os
import sys
import uuid
from unittest import mock

import pytest
from click.testing import CliRunner

from keep.action.action import ActionStatus
from keep.alertmanager.alertmanager import AlertManager
from keep.cli.cli import cli


@mock.patch.dict(
    os.environ, {"KEEP_STATE_FILE": f"tmpstate{uuid.uuid4()}.json"}, clear=True
)
def test_condition():
    """Test that if condition apply to true, alert fired"""
    alert_manager = AlertManager()
    alerts = alert_manager.get_alerts(alert_path="tests/alerts/one_until_resolved.yaml")
    alert = alerts[0]
    # Set the assert to True so it will be triggered
    alert.alert_actions.conditions[0]["assert"] = "True"
    # trigger first alert and check it triggered
    alert.run()
    assert alert.status == ActionStatus.FIRED
    # Set the assert to False so it will not be triggered
    alert.alert_actions.conditions[0]["assert"] = "False"
    # trigger first alert and check it triggered
    alert.run()
    assert alert.status == ActionStatus.RESOLVED
