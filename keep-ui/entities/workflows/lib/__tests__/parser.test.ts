import {
  parseWorkflow,
  getYamlWorkflowDefinition,
  getYamlActionFromAction,
  getYamlStepFromStep,
  getYamlConditionFromStep,
} from "../parser";
import { Provider } from "@/shared/api/providers";
import { Definition, V2StepForeach } from "@/entities/workflows";
import {
  YamlAssertCondition,
  YamlStepOrAction,
  YamlThresholdCondition,
  YamlWorkflowDefinition,
} from "@/entities/workflows/model/yaml.types";
import { getOrderedWorkflowYamlStringFromJSON } from "../yaml-utils";

const mockProviders: Provider[] = [
  {
    type: "clickhouse",
    query_params: ["query", "single_row"],
    notify_params: [],
    config: {},
    installed: true,
    linked: true,
    last_alert_received: "",
    details: { authentication: {}, name: "" },
    id: "clickhouse",
    display_name: "Clickhouse",
    can_query: true,
    can_notify: false,
    tags: ["data"],
    validatedScopes: {},
    pulling_available: false,
    pulling_enabled: true,
    categories: ["Database"],
    coming_soon: false,
    health: true,
  },
  {
    type: "ntfy",
    query_params: [],
    notify_params: ["message", "topic"],
    config: {},
    installed: true,
    linked: true,
    last_alert_received: "",
    details: { authentication: {}, name: "" },
    id: "ntfy",
    display_name: "Ntfy",
    can_query: false,
    can_notify: true,
    tags: ["messaging"],
    validatedScopes: {},
    pulling_available: false,
    pulling_enabled: true,
    categories: ["Collaboration"],
    coming_soon: false,
    health: true,
  },
  {
    type: "slack",
    query_params: [],
    notify_params: ["message"],
    config: {},
    installed: true,
    linked: true,
    last_alert_received: "",
    details: { authentication: {}, name: "" },
    id: "slack",
    display_name: "Slack",
    can_query: false,
    can_notify: true,
    tags: ["messaging"],
    validatedScopes: {},
    pulling_available: false,
    pulling_enabled: true,
    categories: ["Collaboration"],
    coming_soon: false,
    health: true,
  },
];

const workflowWithConditionsAndAliases = `
workflow:
  id: query-victoriametrics
  name: victoriametrics
  description: victoriametrics
  disabled: false
  triggers:
    - type: manual
  consts: {}
  owners: []
  services: []
  steps:
    - name: victoriametrics-step
      provider:
        type: victoriametrics
        config: "{{ providers.victoriametrics }}"
        with:
          query: avg(rate(process_cpu_seconds_total))
          queryType: query
  actions:
    - name: trigger-slack1
      condition:
        - name: threshold-condition
          type: threshold
          alias: A
          value: "{{ steps.victoriametrics-step.results.data.result.0.value.1 }}"
          compare_to: 0.005
      provider:
        type: slack
        config: "{{ providers.slack }}"
        with:
          message: "Result: {{ steps.victoriametrics-step.results.data.result.0.value.1 }} is greater than 0.0040! 🚨"
    - name: trigger-slack2
      if: "{{ A }}"
      provider:
        type: slack
        config: "{{ providers.slack }}"
        with:
          message: "Result: {{ steps.victoriametrics-step.results.data.result.0.value.1 }} is greater than 0.0040! 🚨"
    - name: trigger-ntfy
      if: "{{ A }}"
      provider:
        type: ntfy
        config: "{{ providers.ntfy }}"
        with:
          message: "Result: {{ steps.victoriametrics-step.results.data.result.0.value.1 }} is greater than 0.0040! 🚨"
          topic: ezhil
`;

describe("Workflow Parser", () => {
  describe("getYamlStepFromStep", () => {
    it("should convert a V2StepStep to a YamlStepOrAction", () => {
      const step = {
        id: "step-1",
        name: "clickhouse-step",
        type: "step-clickhouse",
        componentType: "task" as const,
        properties: {
          config: "clickhouse",
          with: {
            query: "SELECT * FROM test",
            single_row: "True",
          },
          stepParams: ["query", "single_row"],
          actionParams: [],
          if: "{{ steps.clickhouse-step.results.level }} == 'ERROR'",
          vars: {
            message: "{{ steps.clickhouse-step.results.message }}",
            topic: "{{ steps.clickhouse-step.results.topic }}",
          },
        },
      };

      const result = getYamlStepFromStep(step);

      expect(result.name).toBe("clickhouse-step");
      expect(result.provider.type).toBe("clickhouse");
      expect(result.provider.config).toBe("{{ providers.clickhouse }}");
      expect(result.provider.with).toEqual({
        query: "SELECT * FROM test",
        single_row: "True",
      });
      expect(result.if).toBe(
        "{{ steps.clickhouse-step.results.level }} == 'ERROR'"
      );
      expect(result.vars).toEqual({
        message: "{{ steps.clickhouse-step.results.message }}",
        topic: "{{ steps.clickhouse-step.results.topic }}",
      });
    });
  });

  describe("getYamlActionFromAction", () => {
    it("should convert a V2ActionStep to a YamlStepOrAction", () => {
      const action = {
        id: "action-1",
        name: "ntfy-action",
        type: "action-ntfy",
        componentType: "task" as const,
        properties: {
          config: "ntfy",
          with: {
            message: "Test message",
            topic: "test",
          },
          stepParams: [],
          actionParams: ["message", "topic"],
          if: "{{ steps.clickhouse-step.results.level }} == 'ERROR'",
          vars: {
            message: "{{ steps.clickhouse-step.results.message }}",
            topic: "{{ steps.clickhouse-step.results.topic }}",
          },
        },
      };

      const result = getYamlActionFromAction(action);

      expect(result.name).toBe("ntfy-action");
      expect(result.provider.type).toBe("ntfy");
      expect(result.provider.config).toBe("{{ providers.ntfy }}");
      expect(result.provider.with).toEqual({
        message: "Test message",
        topic: "test",
      });
      expect(result.if).toBe(
        "{{ steps.clickhouse-step.results.level }} == 'ERROR'"
      );
      expect(result.vars).toEqual({
        message: "{{ steps.clickhouse-step.results.message }}",
        topic: "{{ steps.clickhouse-step.results.topic }}",
      });
    });
  });

  describe("getYamlConditionFromStep", () => {
    it("should convert a V2StepConditionThreshold to a YamlThresholdCondition", () => {
      const conditionStep = {
        id: "condition-1",
        name: "threshold-condition",
        type: "condition-threshold" as const,
        componentType: "switch" as const,
        properties: {
          value: "{{ steps.clickhouse-step.results.level }}",
          compare_to: "ERROR",
        },
        alias: "error-check",
        branches: {
          true: [],
          false: [],
        },
      };

      const result = getYamlConditionFromStep(
        conditionStep
      ) as YamlThresholdCondition;

      expect(result.type).toBe("threshold");
      expect(result.value).toBe("{{ steps.clickhouse-step.results.level }}");
      expect(result.compare_to).toBe("ERROR");
      expect(result.alias).toBe("error-check");
    });

    it("should convert a V2StepConditionAssert to a YamlAssertCondition", () => {
      const conditionStep = {
        id: "condition-1",
        name: "assert-condition",
        type: "condition-assert" as const,
        componentType: "switch" as const,
        properties: {
          assert: "{{ steps.clickhouse-step.results.level }} == 'ERROR'",
        },
        alias: "error-check",
        branches: {
          true: [],
          false: [],
        },
      };

      const result = getYamlConditionFromStep(
        conditionStep
      ) as YamlAssertCondition;

      expect(result.type).toBe("assert");
      expect(result.assert).toBe(
        "{{ steps.clickhouse-step.results.level }} == 'ERROR'"
      );
      expect(result.alias).toBe("error-check");
    });
  });

  describe("parseWorkflow", () => {
    it("should parse a simple workflow with steps and actions", () => {
      const workflowYaml = `
workflow:
  id: test-workflow
  name: Test Workflow
  description: Test Description
  disabled: false
  consts: {}
  steps:
    - name: clickhouse-step
      provider:
        config: "{{ providers.clickhouse }}"
        type: clickhouse
        with:
          query: "SELECT * FROM test"
          single_row: "True"
  actions:
    - name: ntfy-action
      provider:
        config: "{{ providers.ntfy }}"
        type: ntfy
        with:
          message: "Test message"
          topic: test
`;

      const result = parseWorkflow(workflowYaml, mockProviders);

      expect(result.sequence).toHaveLength(2);
      expect(result.properties.id).toBe("test-workflow");
      expect(result.properties.name).toBe("Test Workflow");
      expect(result.sequence[0].type).toBe("step-clickhouse");
      expect(result.sequence[1].type).toBe("action-ntfy");
    });

    it("should parse a workflow with conditions", () => {
      const result = parseWorkflow(
        workflowWithConditionsAndAliases,
        mockProviders
      );

      expect(result.sequence).toHaveLength(2);
      expect(result.sequence[1].type).toBe("condition-threshold");
      expect(result.sequence[1].branches.true).toHaveLength(3);
      expect(result.sequence[1].branches.false).toHaveLength(0);
      expect(result.sequence[1].branches.true[0].type).toBe("action-slack");
      expect(result.sequence[1].branches.true[1].type).toBe("action-slack");
      expect(result.sequence[1].branches.true[2].type).toBe("action-ntfy");
    });

    it("should parse a workflow with foreach", () => {
      const workflowYaml = `
workflow:
  id: test-workflow
  name: Test Workflow
  description: Test Description
  disabled: false
  consts: {}
  steps:
    - name: clickhouse-step
      provider:
        config: "{{ providers.clickhouse }}"
        type: clickhouse
        with:
          query: "SELECT * FROM test"
          single_row: "True"
  actions:
    - name: ntfy-action
      foreach: "{{ steps.clickhouse-step.results.items }}"
      provider:
        config: "{{ providers.ntfy }}"
        type: ntfy
        with:
          message: "Processing item"
          topic: test
`;

      const result = parseWorkflow(workflowYaml, mockProviders);

      expect(result.sequence).toHaveLength(2);
      expect(result.sequence[1].type).toBe("foreach");
      expect((result.sequence[1] as V2StepForeach).sequence[0].type).toBe(
        "action-ntfy"
      );
    });
  });

  describe("getYamlWorkflowDefinition", () => {
    it("should convert a workflow definition back to YAML format", () => {
      const workflowDefinition: Definition = {
        sequence: [
          {
            id: "step-1",
            name: "clickhouse-step",
            type: "step-clickhouse",
            componentType: "task" as const,
            properties: {
              config: "clickhouse",
              with: {
                query: "SELECT * FROM test",
                single_row: "True",
              },
              stepParams: ["query", "single_row"],
              actionParams: [],
            },
          },
          {
            type: "condition-threshold",
            componentType: "switch",
            id: "a819c748-06ff-42cb-b3bc-e63732ae6b40",
            properties: {
              value: "{{ steps.clickhouse-step.results }}",
              compare_to: "90%",
            },
            name: "threshold-condition",
            branches: {
              true: [
                {
                  id: "action-1",
                  name: "ntfy-action",
                  type: "action-ntfy",
                  componentType: "task" as const,
                  properties: {
                    config: "ntfy",
                    with: {
                      message: "Test message",
                      topic: "test",
                    },
                    stepParams: [],
                    actionParams: ["message", "topic"],
                  },
                },
              ],
              false: [],
            },
          },
          {
            id: "foreach-1",
            name: "Foreach",
            type: "foreach",
            componentType: "container" as const,
            properties: {
              value: "{{ steps.clickhouse-step.results.items }}",
            },
            sequence: [
              {
                id: "console-step",
                name: "Console",
                type: "step-console",
                componentType: "task" as const,
                properties: {
                  with: {
                    message: "{{ item }}",
                  },
                  stepParams: ["message"],
                },
              },
            ],
          },
        ],
        properties: {
          id: "test-workflow",
          name: "Test Workflow",
          description: "Test Description",
          disabled: false,
          consts: {},
          isLocked: true,
        },
      };

      const result = getYamlWorkflowDefinition(
        workflowDefinition
      ) as YamlWorkflowDefinition;

      expect(result.id).toBe("test-workflow");
      expect(result.name).toBe("Test Workflow");
      expect(result.steps).toHaveLength(2);
      expect(result.actions).toHaveLength(1);
      expect(result.steps[0].name).toBe("clickhouse-step");
      expect(result.actions![0].name).toBe("ntfy-action");
      expect(result.actions![0].condition).toHaveLength(1);
      expect(result.actions![0].condition![0].type).toBe("threshold");
      expect(result.steps[1].name).toBe("Console");
      expect(result.steps[1].foreach).toBe(
        "{{ steps.clickhouse-step.results.items }}"
      );
    });

    it("should handle workflow with conditions and foreach", () => {
      const workflowDefinition: Definition = {
        sequence: [
          {
            id: "step-1",
            name: "clickhouse-step",
            type: "step-clickhouse",
            componentType: "task" as const,
            properties: {
              config: "clickhouse",
              with: {
                query: "SELECT * FROM test",
                single_row: "True",
              },
              stepParams: ["query", "single_row"],
              actionParams: [],
            },
          },
          {
            id: "foreach-1",
            name: "Foreach",
            type: "foreach",
            componentType: "container" as const,
            properties: {
              value: "{{ steps.clickhouse-step.results.items }}",
            },
            sequence: [
              {
                id: "condition-1",
                name: "error-check",
                type: "condition-threshold",
                componentType: "switch" as const,
                properties: {
                  value: "{{ steps.clickhouse-step.results.level }}",
                  compare_to: "ERROR",
                },
                branches: {
                  true: [
                    {
                      id: "action-1",
                      name: "ntfy-action",
                      type: "action-ntfy",
                      componentType: "task" as const,
                      properties: {
                        config: "ntfy",
                        with: {
                          message: "Error detected",
                          topic: "errors",
                        },
                        stepParams: [],
                        actionParams: ["message", "topic"],
                      },
                    },
                  ],
                  false: [],
                },
              },
            ],
          },
        ],
        properties: {
          id: "test-workflow",
          name: "Test Workflow",
          description: "Test Description",
          disabled: false,
          consts: {},
          isLocked: true,
        },
      };

      const result = getYamlWorkflowDefinition(
        workflowDefinition
      ) as YamlWorkflowDefinition;

      expect(result.id).toBe("test-workflow");
      expect(result.actions).toHaveLength(1);
      const actions = result.actions!;
      expect(actions).toBeDefined();
      const action = actions[0] as YamlStepOrAction;
      expect(action).toBeDefined();
      expect(action.foreach).toBe("{{ steps.clickhouse-step.results.items }}");
      const condition = action.condition!;
      expect(condition).toBeDefined();
      expect(condition[0].type).toBe("threshold");
    });
  });

  describe("round trip should not change the workflow", () => {
    it("should not change the workflow", () => {
      const workflowYaml = workflowWithConditionsAndAliases;
      const result = parseWorkflow(workflowYaml, mockProviders);
      const resultYamlObject = {
        workflow: getYamlWorkflowDefinition(result),
      };
      const resultYamlString =
        getOrderedWorkflowYamlStringFromJSON(resultYamlObject);
      expect(resultYamlString.trim()).toEqual(workflowYaml.trim());
    });
  });
});
