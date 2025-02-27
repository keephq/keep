from io import StringIO
from keep.functions import cyaml


def test_quotes_preserved_in_query():
    """Test that quotes are preserved in SQL queries."""
    yaml_str = """
    name: clickhouse-step
    with:
      query: "SELECT * FROM logs_table ORDER BY timestamp DESC LIMIT 1;"
    """
    data = cyaml.safe_load(yaml_str)
    dumped_yaml = cyaml.dump(data)
    
    assert dumped_yaml is not None
    assert '"SELECT * FROM logs_table ORDER BY timestamp DESC LIMIT 1;"' in dumped_yaml


def test_quotes_preserved_in_template_strings():
    """Test that quotes are preserved in template strings."""
    yaml_str = """
    provider:
      config: "{{ providers.clickhouse }}"
    """
    data = cyaml.safe_load(yaml_str)
    dumped_yaml = cyaml.dump(data)
    
    assert dumped_yaml is not None
    assert '"{{ providers.clickhouse }}"' in dumped_yaml


def test_quotes_preserved_in_boolean_strings():
    """Test that quotes are preserved in boolean strings."""
    yaml_str = """
    with:
      single_row: "True"
      enabled: "False"
    """
    data = cyaml.safe_load(yaml_str)
    dumped_yaml = cyaml.dump(data)
    
    assert dumped_yaml is not None
    assert '"True"' in dumped_yaml
    assert '"False"' in dumped_yaml


def test_quotes_preserved_in_strings_with_colons():
    """Test that quotes are preserved in strings containing colons."""
    yaml_str = """
    condition: "status: error"
    """
    data = cyaml.safe_load(yaml_str)
    dumped_yaml = cyaml.dump(data)
    
    assert dumped_yaml is not None
    assert '"status: error"' in dumped_yaml


def test_quotes_preserved_in_nested_structures():
    """Test that quotes are preserved in nested structures."""
    yaml_str = """
    actions:
      - name: ntfy-action
        if: "'{{ steps.clickhouse-step.results.level }}' == 'ERROR'"
        provider:
          config: "{{ providers.ntfy }}"
    """
    data = cyaml.safe_load(yaml_str)
    dumped_yaml = cyaml.dump(data)
    
    assert dumped_yaml is not None
    assert '"{{ providers.ntfy }}"' in dumped_yaml
    assert "\"'{{ steps.clickhouse-step.results.level }}' == 'ERROR'\"" in dumped_yaml


def test_unquoted_strings_remain_unquoted():
    """Test that unquoted strings remain unquoted."""
    yaml_str = """
    name: simple-name
    type: simple-type
    """
    data = cyaml.safe_load(yaml_str)
    dumped_yaml = cyaml.dump(data)
    
    assert dumped_yaml is not None
    assert 'name: simple-name' in dumped_yaml
    assert 'type: simple-type' in dumped_yaml
    assert '"simple-name"' not in dumped_yaml
    assert '"simple-type"' not in dumped_yaml


def test_numeric_values_remain_unquoted():
    """Test that numeric values remain unquoted."""
    yaml_str = """
    count: 42
    ratio: 3.14
    """
    data = cyaml.safe_load(yaml_str)
    dumped_yaml = cyaml.dump(data)
    
    assert dumped_yaml is not None
    assert 'count: 42' in dumped_yaml
    assert 'ratio: 3.14' in dumped_yaml
    assert '"42"' not in dumped_yaml
    assert '"3.14"' not in dumped_yaml


def test_complex_yaml_structure():
    """Test a complex YAML structure with various types of values."""
    yaml_str = """
    workflow:
      name: "Complex Workflow"
      description: Simple workflow for testing
      steps:
        - name: step1
          provider:
            type: clickhouse
            config: "{{ providers.clickhouse }}"
          with:
            query: "SELECT * FROM table WHERE status = 'error';"
            single_row: "True"
        - name: step2
          if: "steps.step1.results.count > 0"
          provider:
            type: http
            config: "{{ providers.http }}"
      constants:
        threshold: 100
        message: "Alert: threshold exceeded"
    """
    data = cyaml.safe_load(yaml_str)
    dumped_yaml = cyaml.dump(data)
    
    assert dumped_yaml is not None
    # Check quoted strings are preserved
    assert '"Complex Workflow"' in dumped_yaml
    assert '"{{ providers.clickhouse }}"' in dumped_yaml
    assert '"{{ providers.http }}"' in dumped_yaml
    assert '"SELECT * FROM table WHERE status = \'error\';"' in dumped_yaml
    assert '"True"' in dumped_yaml
    assert '"steps.step1.results.count > 0"' in dumped_yaml
    assert '"Alert: threshold exceeded"' in dumped_yaml
    
    # Check unquoted values remain unquoted
    assert 'description: Simple workflow for testing' in dumped_yaml
    assert 'threshold: 100' in dumped_yaml


def test_stream_output():
    """Test dumping to a stream instead of returning a string."""
    yaml_str = """
    name: "Test Stream"
    query: "SELECT * FROM table;"
    """
    data = cyaml.safe_load(yaml_str)
    
    # Test dumping to a stream
    stream = StringIO()
    result = cyaml.dump(data, stream)
    
    # Check that the result is None (as per the API)
    assert result is None
    
    # Check that the stream contains the expected content
    stream_content = stream.getvalue()
    assert stream_content is not None
    assert '"Test Stream"' in stream_content
    assert '"SELECT * FROM table;"' in stream_content 