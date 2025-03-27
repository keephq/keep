import { validateYamlString } from "../validate-yaml";
import { YamlWorkflowDefinitionSchema } from "@/entities/workflows/model/yaml.schema";

const defaultWorkflowSchema = YamlWorkflowDefinitionSchema;

describe("validateWorkflowYaml", () => {
  it("should validate a correct workflow YAML", () => {
    const validYaml = `workflow:
  id: test-workflow
  name: Test Workflow
  description: A test workflow
  disabled: false
  triggers:
    - type: manual
  steps:
    - name: test-step
      provider:
        type: clickhouse
        config: default
        with:
          query: SELECT 1
          single_row: true`;

    const result = validateYamlString(validYaml, defaultWorkflowSchema);
    expect(result.valid).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.errors).toBeUndefined();
  });

  it("should validate a workflow with all optional fields", () => {
    const validYaml = `workflow:
  id: test-workflow
  name: Test Workflow
  triggers:
    - type: manual
  description: A test workflow
  disabled: false
  owners: ["owner1", "owner2"]
  services: ["service1", "service2"]
  consts:
    key1: value1
    key2: value2
  steps:
    - name: test-step
      provider:
        type: clickhouse
        config: default
        with:
          query: SELECT 1
          single_row: true
  actions:
    - name: test-action
      provider:
        type: ntfy
        config: default
        with:
          message: test
          topic: alerts`;

    const result = validateYamlString(validYaml, defaultWorkflowSchema);
    expect(result.valid).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.errors).toBeUndefined();
  });

  it("should detect missing required fields with line positions", () => {
    const invalidYaml = `workflow:
  name: Test Workflow
  description: A test workflow
  steps:
    - provider:
        type: clickhouse
        config: default
        with:
          query: SELECT 1`;

    const result = validateYamlString(invalidYaml, defaultWorkflowSchema);
    expect(result.valid).toBe(false);
    expect(result.errors).toBeDefined();
    expect(result.errors).toEqual(
      expect.arrayContaining([
        {
          col: 4,
          line: 2,
          message: "'id' field is required in 'workflow'",
          path: ["workflow", "id"],
        },
        {
          col: 8,
          line: 5,
          message: "'name' field is required in 'steps entries'",
          path: ["workflow", "steps", 0, "name"],
        },
        {
          col: 4,
          line: 2,
          message: "'triggers' field is required in 'workflow'",
          path: ["workflow", "triggers"],
        },
      ])
    );
  });

  it("should validate workflow with conditions", () => {
    const yamlWithConditions = `workflow:
  id: test-workflow
  name: Test Workflow
  triggers:
    - type: manual
  steps:
    - name: test-step
      provider:
        type: clickhouse
        config: default
        with:
          query: SELECT 1
      condition:
        - name: threshold-check
          type: threshold
          value: "{{ steps.test-step.results }}"
          compare_to: "90%"
        - name: assert-check
          type: assert
          assert: "{{ steps.test-step.results > 0 }}"`;

    const result = validateYamlString(
      yamlWithConditions,
      defaultWorkflowSchema
    );
    expect(result.valid).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.errors).toBeUndefined();
  });

  it("should detect invalid condition type", () => {
    const invalidYaml = `workflow:
  id: test-workflow
  name: Test Workflow
  triggers:
    - type: manual
  steps:
    - name: test-step
      provider:
        type: clickhouse
        config: default
        with:
          query: SELECT 1
      condition:
        - name: invalid-check
          type: invalid
          value: test`;

    const result = validateYamlString(invalidYaml, defaultWorkflowSchema);
    expect(result.valid).toBe(false);
    expect(result.errors).toBeDefined();
    expect(result.errors).toEqual(
      expect.arrayContaining([
        {
          path: ["workflow", "steps", 0, "condition", 0],
          message: "Invalid input",
          line: 14,
          col: 12,
        },
      ])
    );
  });

  it("should validate workflow with foreach", () => {
    const yamlWithForeach = `workflow:
  id: test-workflow
  name: Test Workflow
  triggers:
    - type: manual
  steps:
    - name: test-step
      provider:
        type: clickhouse
        config: default
        with:
          query: SELECT 1
      foreach: "{{ steps.previous-step.results.items }}"`;

    const result = validateYamlString(yamlWithForeach, defaultWorkflowSchema);
    expect(result.valid).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.errors).toBeUndefined();
  });

  it("should validate workflow with variables", () => {
    const yamlWithVars = `workflow:
  id: test-workflow
  name: Test Workflow
  triggers:
    - type: manual
  steps:
    - name: test-step
      provider:
        type: clickhouse
        config: default
        with:
          query: SELECT 1
      vars:
        var1: "{{ steps.previous-step.results }}"
        var2: "static-value"`;

    const result = validateYamlString(yamlWithVars, defaultWorkflowSchema);
    expect(result.valid).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.errors).toBeUndefined();
  });

  it("should validate workflow with invalid provider and return proper column and line", () => {
    const invalidYaml = `workflow:
  id: test-workflow
  name: Test Workflow
  triggers:
    - type: manual
  steps:
    - name: test-step
      provider:
        config: default
        with:
          query: SELECT 1`;

    const result = validateYamlString(invalidYaml, defaultWorkflowSchema);
    expect(result.valid).toBe(false);
    expect(result.errors).toBeDefined();
    expect(result.errors).toEqual(
      expect.arrayContaining([
        {
          col: 10,
          line: 9,
          message: "'type' field is required in 'provider'",
          path: ["workflow", "steps", 0, "provider", "type"],
        },
      ])
    );
  });
});
