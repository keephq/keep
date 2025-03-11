import { validateWorkflowYaml } from "../validate-yaml";

describe("validateWorkflowYaml", () => {
  it("should validate a correct workflow YAML", () => {
    const validYaml = `workflow:
  id: test-workflow
  name: Test Workflow
  description: A test workflow
  disabled: false
  steps:
    - name: test-step
      provider:
        type: clickhouse
        config: default
        with:
          query: SELECT 1
          single_row: true`;

    const result = validateWorkflowYaml(validYaml);
    expect(result.valid).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.errors).toBeUndefined();
  });

  it("should validate a workflow with all optional fields", () => {
    const validYaml = `workflow:
  id: test-workflow
  name: Test Workflow
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

    const result = validateWorkflowYaml(validYaml);
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

    const result = validateWorkflowYaml(invalidYaml);
    expect(result.valid).toBe(false);
    expect(result.errors).toBeDefined();
    expect(result.errors).toEqual(
      expect.arrayContaining([
        {
          path: ["workflow", "id"],
          message: "Required",
        },
        {
          path: ["workflow", "steps", 0, "name"],
          message: "Required",
        },
      ])
    );
  });

  it("should validate workflow with conditions", () => {
    const yamlWithConditions = `workflow:
  id: test-workflow
  name: Test Workflow
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

    const result = validateWorkflowYaml(yamlWithConditions);
    expect(result.valid).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.errors).toBeUndefined();
  });

  it("should detect invalid condition type", () => {
    const invalidYaml = `workflow:
  id: test-workflow
  name: Test Workflow
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

    const result = validateWorkflowYaml(invalidYaml);
    expect(result.valid).toBe(false);
    expect(result.errors).toBeDefined();
    expect(result.errors).toEqual(
      expect.arrayContaining([
        {
          path: ["workflow", "steps", 0, "condition", 0],
          message: "Invalid input",
          line: 12,
          col: 11,
        },
      ])
    );
  });

  it("should validate workflow with foreach", () => {
    const yamlWithForeach = `workflow:
  id: test-workflow
  name: Test Workflow
  steps:
    - name: test-step
      provider:
        type: clickhouse
        config: default
        with:
          query: SELECT 1
      foreach: "{{ steps.previous-step.results.items }}"`;

    const result = validateWorkflowYaml(yamlWithForeach);
    expect(result.valid).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.errors).toBeUndefined();
  });

  it("should validate workflow with variables", () => {
    const yamlWithVars = `workflow:
  id: test-workflow
  name: Test Workflow
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

    const result = validateWorkflowYaml(yamlWithVars);
    expect(result.valid).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.errors).toBeUndefined();
  });

  it("should validate workflow with invalid provider and return proper column and line", () => {
    const invalidYaml = `workflow:
  id: test-workflow
  name: Test Workflow
  steps:
    - name: test-step
      provider:
        config: default
        with:
          query: SELECT 1`;

    const result = validateWorkflowYaml(invalidYaml);
    expect(result.valid).toBe(false);
    expect(result.errors).toBeDefined();
    expect(result.errors).toEqual(
      expect.arrayContaining([
        {
          path: ["workflow", "steps", 0, "provider"],
          message: "Invalid input",
          line: 6,
          col: 16,
        },
      ])
    );
  });
});
