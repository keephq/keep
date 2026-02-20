from click.testing import CliRunner

from keep.cli.cli import cli


def _write_valid_workflow(path):
    path.write_text(
        """workflow:
  id: cli-validate-test
  name: CLI Validate Test
  triggers:
    - type: manual
  steps:
    - name: console-step
      provider:
        type: console
        with:
          message: hello
""",
        encoding="utf-8",
    )


def test_workflow_validate_single_file_success(tmp_path):
    workflow_file = tmp_path / "workflow.yml"
    _write_valid_workflow(workflow_file)

    runner = CliRunner()
    result = runner.invoke(cli, ["workflow", "validate", "-f", str(workflow_file)])

    assert result.exit_code == 0
    assert "Validation summary: 1 passed, 0 failed" in result.output


def test_workflow_validate_single_file_failure(tmp_path):
    workflow_file = tmp_path / "invalid.yml"
    workflow_file.write_text("workflow: [", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["workflow", "validate", "-f", str(workflow_file)])

    assert result.exit_code == 1
    assert "Validation summary: 0 passed, 1 failed" in result.output


def test_workflow_validate_directory_mixed_results(tmp_path):
    _write_valid_workflow(tmp_path / "good.yml")
    (tmp_path / "bad.yaml").write_text("workflow: [", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("not a workflow", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["workflow", "validate", "-d", str(tmp_path)])

    assert result.exit_code == 1
    assert "Validation summary: 1 passed, 1 failed" in result.output
