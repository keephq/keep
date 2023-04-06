import io
import logging
import os
import sys

import pytest
from click.testing import CliRunner

from keep.cli.cli import run


def alert_test(alert_file_name):
    runner = CliRunner()
    alert_path = os.path.join("examples/alerts", alert_file_name)
    result = runner.invoke(run, ["--alerts-file", alert_path])
    return result


def generate_test_cases():
    test_cases = os.listdir("examples/alerts")
    return test_cases


@pytest.mark.parametrize("alert_file_name", generate_test_cases())
def test_multiplication(caplog, alert_file_name):
    result = alert_test(alert_file_name)
    assert result.exit_code == 0


def test_all_alerts_in_alerts_directory_are_parsed(caplog):
    runner = CliRunner()
    result = runner.invoke(run, ["--alerts-directory", "examples/alerts"])
    assert result.exit_code == 0
