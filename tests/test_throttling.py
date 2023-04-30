import io
import logging
import os
import sys

import pytest
from click.testing import CliRunner

from keep.cli.cli import cli


def test_throttle_sanity(caplog, capsys):
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
    for log in logs:
        if "is throttled" in log:
            throttled = True
            break

    assert throttled == True
