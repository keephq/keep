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
def test_throttle_sanity():
    """Tests end-to-end (cli -> alertmanager -> action) for a single alert"""
    # trigger first alert and check it triggered
    runner = CliRunner()
    result = runner.invoke(
        cli,
        args=["-vvv", "run", "--alerts-file", "tests/alerts/one_until_resolved.yaml"],
    )
    # Validate the exit code is 0
    assert result.exit_code == 0
    # Validate the mock action is evaluated to run
    logs = result.output.splitlines()
    evaluated_to_run = False
    for log in logs:
        if "Action is not throttled" in log:
            evaluated_to_run = True
            break

    assert evaluated_to_run == True
    result = runner.invoke(
        cli,
        args=["-vvv", "run", "--alerts-file", "tests/alerts/one_until_resolved.yaml"],
    )
    # Validate the exit code is 0
    assert result.exit_code == 0
    throttled = False
    logs = result.output.splitlines()
    # verify that the action is throttled
    for log in logs:
        if "is throttled" in log:
            throttled = True
            break

    assert throttled == True


@mock.patch.dict(
    os.environ, {"KEEP_STATE_FILE": f"tmpstate{uuid.uuid4()}.json"}, clear=True
)
def test_throttle_resolve():
    alert_manager = AlertManager()
    alerts = alert_manager.get_alerts(alert_path="tests/alerts/one_until_resolved.yaml")
    alert = alerts[0]
    # trigger first alert and check it triggered
    alert.run()
    # Validate the mock action is evaluated to run
    assert alert.alert_actions[0].status == ActionStatus.FIRING
    # Run it again
    alert.run()
    # Validate the mock action is evaluated to run
    assert alert.alert_actions[0].status == ActionStatus.THROTTLED

    # Resolve
    alert.alert_steps[0].step_config["provider"]["with"]["command"] = "true"
    alert.run()
    assert alert.alert_actions[0].status == ActionStatus.SKIPPED

    # Now rerun
    alert.alert_steps[0].step_config["provider"]["with"]["command"] = "stat notfound"
    alert.run()
    assert alert.alert_actions[0].status == ActionStatus.FIRING

    # Remove the tmpstate file
    os.remove(os.environ["KEEP_STATE_FILE"])
