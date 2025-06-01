import { Definition, V2ActionStep, V2Step } from "../../model/types";
import {
  validateAllMustacheVariablesInString,
  validateMustacheVariableName,
} from "../validate-definition";

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
    const result = validateMustacheVariableName(
      "{{ alert.name }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBeNull();
  });

  it("should validate incident variables", () => {
    const result = validateMustacheVariableName(
      "{{ incident.title }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBeNull();
  });

  it("should validate step results access", () => {
    const result = validateMustacheVariableName(
      "{{ steps.First Step.results }}",
      mockDefinition.sequence[1],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBeNull();
  });

  it("should prevent accessing current step results", () => {
    const result = validateMustacheVariableName(
      "{{ steps.First Step.results }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBe(
      "Variable: '{{ steps.First Step.results }}' - You can't access the results of the current step."
    );
  });

  it("should prevent accessing future step results", () => {
    const result = validateMustacheVariableName(
      "{{ steps.Second Step.results }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBe(
      "Variable: '{{ steps.Second Step.results }}' - You can't access the results of a step that appears after the current step."
    );
  });

  it("should prevent accessing action results from a step", () => {
    const result = validateMustacheVariableName(
      "{{ steps.Second Step.results }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toBe(
      "Variable: '{{ steps.Second Step.results }}' - You can't access the results of a step that appears after the current step."
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
    },
  };
  const mockSecrets = {};

  it("should validate multiple variables in a string", () => {
    const result = validateAllMustacheVariablesInString(
      "Alert: {{ alert.name }} with severity {{ alert.severity }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toEqual([]);
  });

  it("should detect invalid variables in a string", () => {
    const result = validateAllMustacheVariablesInString(
      "Invalid: {{ invalid.var }} and {{ steps.Future Step.results }}",
      mockDefinition.sequence[0],
      mockDefinition,
      mockSecrets
    );
    expect(result).toContain(
      "Variable: '{{ steps.Future Step.results }}' - a 'Future Step' step that doesn't exist."
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
    const result = validateAllMustacheVariablesInString(
      "keep.dictget({{steps.python-step.results}} , '{{foreach.value.fingerprint}}', 'default') == '{{foreach.value.fingerprint}}'",
      telegramAction, // telegram step
      definition,
      mockSecrets
    );
    expect(result).toEqual([]);
  });
});
