import pytest
import tempfile
import os
from click.testing import CliRunner
from keep.cli.cli import cli


class TestWorkflowValidation:
    """Comprehensive tests for the workflow validate command"""
    
    def test_validate_valid_workflow_with_steps(self):
        """Test validation with a valid workflow containing steps"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: test-workflow
  name: Test Workflow
  description: A test workflow
  triggers:
    - type: manual
  steps:
    - name: test-step
      provider:
        type: bash
        with:
          command: echo "test"
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 0
                assert "Workflow syntax is valid" in result.output
                assert "test-workflow" in result.output
                assert "Steps: 1" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_valid_workflow_with_actions(self):
        """Test validation with a valid workflow containing only actions"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: action-workflow
  name: Action Workflow
  triggers:
    - type: alert
  actions:
    - name: dismiss-alert
      provider:
        type: mock
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 0
                assert "Actions: 1" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_workflow_with_steps_and_actions(self):
        """Test validation with workflow containing both steps and actions"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: mixed-workflow
  name: Mixed Workflow
  triggers:
    - type: manual
  steps:
    - name: step1
  actions:
    - name: action1
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 0
                assert "Steps: 1" in result.output
                assert "Actions: 1" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_missing_id(self):
        """Test validation with missing id field"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  name: Test Workflow
  triggers:
    - type: manual
  steps:
    - name: test-step
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                assert "Missing required field: id" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_missing_name(self):
        """Test validation with missing name field"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: test-id
  triggers:
    - type: manual
  steps:
    - name: test-step
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                assert "Missing required field: name" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_empty_id(self):
        """Test validation with empty id field"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: ""
  name: Test Workflow
  triggers:
    - type: manual
  steps:
    - name: test-step
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                assert "must be a non-empty string" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_missing_workflow_key(self):
        """Test validation with missing workflow key"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""id: test
name: Test
triggers:
  - type: manual
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                assert "Missing top-level 'workflow' key" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_empty_triggers(self):
        """Test validation with empty triggers list"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: test-workflow
  name: Test Workflow
  triggers: []
  steps:
    - name: test-step
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                assert "Workflow must contain at least one trigger" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_missing_triggers(self):
        """Test validation with missing triggers field"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: test-workflow
  name: Test Workflow
  steps:
    - name: test-step
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                assert "Missing required field: triggers" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_no_steps_or_actions(self):
        """Test validation with neither steps nor actions"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: empty-workflow
  name: Empty Workflow
  triggers:
    - type: manual
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                assert "Workflow must contain at least one step or action" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_trigger_without_type(self):
        """Test validation with trigger missing type field"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: test-workflow
  name: Test Workflow
  triggers:
    - filters:
        - key: severity
          value: critical
  steps:
    - name: test-step
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                assert "is missing 'type' field" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_step_without_name(self):
        """Test validation with step missing name field"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: test-workflow
  name: Test Workflow
  triggers:
    - type: manual
  steps:
    - provider:
        type: bash
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                assert "is missing 'name' field" in result.output
            finally:
                os.unlink(f.name)
    
    def test_validate_invalid_yaml_syntax(self):
        """Test validation with invalid YAML syntax"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("""workflow:
  id: test
  name: Test
  triggers: [
    - type: manual
  steps:
""")
            f.flush()
            
            try:
                result = runner.invoke(cli, ['workflow', 'validate', '--file', f.name])
                assert result.exit_code == 1
                # Should catch YAML parsing error
                assert "Invalid" in result.output or "error" in result.output.lower()
            finally:
                os.unlink(f.name)
    
    def test_validate_file_not_found(self):
        """Test validation with non-existent file"""
        runner = CliRunner()
        result = runner.invoke(cli, ['workflow', 'validate', '--file', 'nonexistent.yaml'])
        # File existence is checked by click.Path(exists=True), so this should fail before our code runs
        assert result.exit_code != 0
    
    def test_validate_real_workflow_examples(self):
        """Test validation with real workflow examples from the repo"""
        runner = CliRunner()
        example_files = [
            'examples/workflows/bash_example.yml',
            'examples/workflows/autosupress.yml',
        ]
        
        for workflow_file in example_files:
            if os.path.exists(workflow_file):
                result = runner.invoke(cli, ['workflow', 'validate', '--file', workflow_file])
                assert result.exit_code == 0, f"Failed to validate {workflow_file}: {result.output}"
                assert "Workflow syntax is valid" in result.output
