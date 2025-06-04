import { Definition, V2ActionStep, V2Step } from "../../model/types";
import {
  validateAllMustacheVariablesForUIBuilderStep,
  validateMustacheVariableForUIBuilderStep,
} from "../validate-mustache-ui-builder";

describe("validateMustacheVariableName", () => {
  const mockDefinition: Definition = {
    sequence: [
      {
        id: "step1",
        name: "First Step",
        componentType: "task",
        type: "step-test",
        properties: {
          actionParams: [],
          stepParams: [],
        },
      },
      {
        id: "step2",
        name: "Second Step",
        componentType: "task",
        type: "action-test",
        properties: {
          actionParams: [],
          stepParams: [],
        },
      },
    ],
    properties: {
      id: "test-workflow",
      name: "Test Workflow",
      description: "Test Description",
      disabled: false,
      isLocked: false,
      consts: {},
    },
  };
  const mockSecrets = {};

  it("should validate alert variables", () => {
    const result = validateMustacheVariableForUIBuilderStep(
      "alert.name",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBeNull();
  });

  it("should validate incident variables", () => {
    const result = validateMustacheVariableForUIBuilderStep(
      "incident.title",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBeNull();
  });

  it("should validate step results access", () => {
    const result = validateMustacheVariableForUIBuilderStep(
      "steps.First Step.results",
      mockDefinition.sequence[1],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBeNull();
  });

  it("should prevent accessing current step results", () => {
    const result = validateMustacheVariableForUIBuilderStep(
      "steps.First Step.results",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBe(
      "Variable: 'steps.First Step.results' - You can't access the results of the current step."
    );
  });

  it("should prevent accessing future step results", () => {
    const result = validateMustacheVariableForUIBuilderStep(
      "steps.Second Step.results",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBe(
      "Variable: 'steps.Second Step.results' - You can't access the results of a step that appears after the current step."
    );
  });

  it("should prevent accessing action results from a step", () => {
    const result = validateMustacheVariableForUIBuilderStep(
      "steps.Second Step.results",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBe(
      "Variable: 'steps.Second Step.results' - You can't access the results of a step that appears after the current step."
    );
  });
});

describe("validateAllMustacheVariablesInString", () => {
  const mockDefinition: Definition = {
    sequence: [
      {
        id: "step1",
        name: "First Step",
        componentType: "task",
        type: "step-test",
        properties: {
          actionParams: [],
          stepParams: [],
        },
      },
    ],
    properties: {
      id: "test-workflow",
      name: "Test Workflow",
      description: "Test Description",
      disabled: false,
      isLocked: false,
      consts: {},
      inputs: [
        {
          name: "test",
          description: "Test Input",
          type: "string",
        },
      ],
    },
  };
  const mockSecrets = {};

  it("should validate multiple variables in a string", () => {
    const result = validateAllMustacheVariablesForUIBuilderStep(
      "Alert: {{ alert.name }} with severity {{ alert.severity }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toEqual([]);
  });

  it("should detect invalid variables in a string", () => {
    const result = validateAllMustacheVariablesForUIBuilderStep(
      "Invalid: {{ invalid.var }} and {{ steps.Future Step.results }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toContain(
      "Variable: 'steps.Future Step.results' - a 'Future Step' step that doesn't exist."
    );
  });

  it("should validate reference of variable in step in foreach container", () => {
    const telegramAction: V2ActionStep = {
      id: "telegram-action",
      name: "telegram-action",
      componentType: "task",
      type: "step-telegram",
      properties: {
        if: "keep.dictget({{steps.python-step.results}} , '{{foreach.value.fingerprint}}', 'default') == '{{foreach.value.fingerprint}}'",
        actionParams: ["message"],
        with: {
          message: "{{ foreach.value }}",
        },
      },
    };
    const definition: Definition = {
      sequence: [
        {
          id: "step1",
          name: "python-step",
          componentType: "task",
          type: "step-python",
          properties: {
            actionParams: [],
            stepParams: ["code"],
            with: {
              code: "[x for x in range(100)]",
            },
          },
        },
        {
          id: "foreach-step",
          name: "foreach-step",
          componentType: "container",
          type: "foreach",
          properties: {
            value: "{{ steps.python-step.results }}",
          },
          sequence: [telegramAction],
        },
      ],
      properties: {
        id: "test-workflow",
        name: "Test Workflow",
        description: "Test Description",
        disabled: false,
        isLocked: false,
        consts: {},
      },
    };
    const result = validateAllMustacheVariablesForUIBuilderStep(
      "keep.dictget({{steps.python-step.results}} , '{{foreach.value.fingerprint}}', 'default') == '{{foreach.value.fingerprint}}'",
      telegramAction, // telegram step
      definition,
      mockSecrets
    );
    expect(result).toEqual([]);

    // short syntax
    const result2 = validateAllMustacheVariablesForUIBuilderStep(
      "{{ . }}",
      telegramAction, // telegram step
      definition,
      mockSecrets
    );
    expect(result2).toEqual([]);

    const result3 = validateAllMustacheVariablesForUIBuilderStep(
      "{{ foreach.value }}",
      telegramAction,
      definition,
      mockSecrets
    );
    expect(result3).toEqual([]);

    const result4 = validateAllMustacheVariablesForUIBuilderStep(
      "{{ value }}",
      telegramAction,
      definition,
      mockSecrets
    );
    expect(result4).toEqual([]);
  });

  it("should return an error if bracket notation is used", () => {
    const result = validateAllMustacheVariablesForUIBuilderStep(
      "{{ steps['python-step'].results }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toEqual([
      "Variable: 'steps[\'python-step\'].results' - bracket notation is not supported, use dot notation instead.",
    ]);
  });

  it("should validate vars variables", () => {
    const step: V2Step = {
      id: "step1",
      name: "First Step",
      componentType: "task",
      type: "step-test",
      properties: {
        actionParams: [],
        stepParams: [],
        vars: { test: "test" },
      },
    };
    const definition = {
      ...mockDefinition,
      sequence: [step],
    };
    const result = validateAllMustacheVariablesForUIBuilderStep(
      "{{ vars.test }}",
      step,
      definition,
      mockSecrets
    );
    expect(result).toEqual([]);
  });

  it("should return an error if vars variable is not found", () => {
    const result = validateAllMustacheVariablesForUIBuilderStep(
      "{{ vars.test }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toEqual([
      "Variable: 'vars.test' - Variable 'test' not found in step definition.",
    ]);
  });

  it("should return an error for unknown variables", () => {
    const result = validateAllMustacheVariablesForUIBuilderStep(
      "{{ unknown.var }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toEqual(["Variable: 'unknown.var' - unknown variable."]);
  });

  it("should validate inputs variable", () => {
    const result = validateAllMustacheVariablesForUIBuilderStep(
      "{{ inputs.test }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toEqual([]);
  });

  it("should return an error if inputs variable is not found", () => {
    const result = validateAllMustacheVariablesForUIBuilderStep(
      "{{ inputs.missing }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toEqual([
      "Variable: 'inputs.missing' - Input 'missing' not defined. Available inputs: test",
    ]);
  });
});
