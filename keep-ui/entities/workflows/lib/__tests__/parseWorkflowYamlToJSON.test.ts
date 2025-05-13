import { YamlWorkflowDefinitionSchema } from "@/entities/workflows/model/yaml.schema";
import { parseWorkflowYamlToJSON } from "../yaml-utils";

const defaultWorkflowSchema = YamlWorkflowDefinitionSchema;

describe("parseWorkflowYamlToJSON", () => {
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

    const result = parseWorkflowYamlToJSON(validYaml, defaultWorkflowSchema);
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.error).toBeUndefined();
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

    const result = parseWorkflowYamlToJSON(validYaml, defaultWorkflowSchema);
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.error).toBeUndefined();
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

    const result = parseWorkflowYamlToJSON(invalidYaml, defaultWorkflowSchema);
    expect(result.success).toBe(false);
    expect(result.error).toBeDefined();
    expect(result.error?.issues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          path: ["workflow", "id"],
          message: "Required",
        }),
        expect.objectContaining({
          path: ["workflow", "steps", 0, "name"],
          message: "Required",
        }),
        expect.objectContaining({
          path: ["workflow", "triggers"],
          message: "Required",
        }),
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

    const result = parseWorkflowYamlToJSON(
      yamlWithConditions,
      defaultWorkflowSchema
    );
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.error).toBeUndefined();
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

    const result = parseWorkflowYamlToJSON(invalidYaml, defaultWorkflowSchema);
    expect(result.success).toBe(false);
    expect(result.error).toBeDefined();
    expect(result.error?.issues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          path: ["workflow", "steps", 0, "condition", 0],
          message: "Invalid input",
        }),
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

    const result = parseWorkflowYamlToJSON(
      yamlWithForeach,
      defaultWorkflowSchema
    );
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.error).toBeUndefined();
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

    const result = parseWorkflowYamlToJSON(yamlWithVars, defaultWorkflowSchema);
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.error).toBeUndefined();
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

    const result = parseWorkflowYamlToJSON(invalidYaml, defaultWorkflowSchema);
    expect(result.success).toBe(false);
    expect(result.error).toBeDefined();
    expect(result.error?.issues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          path: ["workflow", "steps", 0, "provider", "type"],
          message: "Required",
        }),
      ])
    );
  });

  it("should validate workflow with global on-failure", () => {
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
        var2: "static-value"
  on-failure:
    retry:
      count: 2
      interval: 2`;

    const result = parseWorkflowYamlToJSON(yamlWithVars, defaultWorkflowSchema);
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.error).toBeUndefined();
  });

  it("should validate workflow with global on-failure with provider", () => {
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
        var2: "static-value"
  on-failure:
    provider:
      type: ntfy
      config: default
      with:
        message: test
        topic: alerts
    retry:
      count: 2
      interval: 2`;

    const result = parseWorkflowYamlToJSON(yamlWithVars, defaultWorkflowSchema);
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.error).toBeUndefined();
  });

  it("should validate workflow with just provider in on-failure", () => {
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
        var2: "static-value"
  on-failure:
    provider:
      type: ntfy
      config: default
      with:
        message: test
        topic: alerts`;

    const result = parseWorkflowYamlToJSON(yamlWithVars, defaultWorkflowSchema);
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.error).toBeUndefined();
  });

  it("should validate workflow with step-level on-failure", () => {
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
        on-failure:
          retry:
            count: 2
            interval: 2
      vars:
        var1: "{{ steps.previous-step.results }}"
        var2: "static-value"`;

    const result = parseWorkflowYamlToJSON(yamlWithVars, defaultWorkflowSchema);
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.error).toBeUndefined();
  });
});
