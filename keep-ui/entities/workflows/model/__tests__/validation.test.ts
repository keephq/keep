import {
  validateMustacheVariableName,
  validateAllMustacheVariablesInString,
  validateStepPure,
  validateGlobalPure,
} from "../validation";
import { Provider } from "@/shared/api/providers";
import { Definition, V2Step } from "../types";

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

  it("should validate alert variables", () => {
    const result = validateMustacheVariableName(
      "{{ alert.name }}",
      mockDefinition.sequence[0],
      mockDefinition
    );
    expect(result).toBeNull();
  });

  it("should validate incident variables", () => {
    const result = validateMustacheVariableName(
      "{{ incident.title }}",
      mockDefinition.sequence[0],
      mockDefinition
    );
    expect(result).toBeNull();
  });

  it("should validate step results access", () => {
    const result = validateMustacheVariableName(
      "{{ steps.First Step.results }}",
      mockDefinition.sequence[1],
      mockDefinition
    );
    expect(result).toBeNull();
  });

  it("should prevent accessing current step results", () => {
    const result = validateMustacheVariableName(
      "{{ steps.First Step.results }}",
      mockDefinition.sequence[0],
      mockDefinition
    );
    expect(result).toBe(
      "Variable: '{{ steps.First Step.results }}' - You can't access the results of the current step."
    );
  });

  it("should prevent accessing future step results", () => {
    const result = validateMustacheVariableName(
      "{{ steps.Second Step.results }}",
      mockDefinition.sequence[0],
      mockDefinition
    );
    expect(result).toBe(
      "Variable: '{{ steps.Second Step.results }}' - You can't access the results of a step that appears after the current step."
    );
  });

  it("should prevent accessing action results from a step", () => {
    const result = validateMustacheVariableName(
      "{{ steps.Second Step.results }}",
      mockDefinition.sequence[0],
      mockDefinition
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

  it("should validate multiple variables in a string", () => {
    const result = validateAllMustacheVariablesInString(
      "Alert: {{ alert.name }} with severity {{ alert.severity }}",
      mockDefinition.sequence[0],
      mockDefinition
    );
    expect(result).toEqual([]);
  });

  it("should detect invalid variables in a string", () => {
    const result = validateAllMustacheVariablesInString(
      "Invalid: {{ invalid.var }} and {{ steps.Future Step.results }}",
      mockDefinition.sequence[0],
      mockDefinition
    );
    expect(result).toContain(
      "Variable: '{{ steps.Future Step.results }}' - a 'Future Step' step that doesn't exist."
    );
  });
});

describe("validateStepPure", () => {
  const mockProviders: Provider[] = [
    {
      type: "test",
      config: {
        api_key: {
          description: "API Key",
          required: true,
          sensitive: true,
          default: null,
        },
      },
      details: {
        name: "test-config",
        authentication: {
          api_key: "test-key",
        },
      },
      id: "test-provider",
      display_name: "Test Provider",
      can_query: false,
      can_notify: false,
      tags: [],
      validatedScopes: {},
      pulling_available: false,
      pulling_enabled: true,
      categories: ["Others"],
      coming_soon: false,
      health: false,
      installed: true,
      linked: true,
      last_alert_received: "",
    },
  ];

  const mockInstalledProviders: Provider[] = [
    {
      type: "test",
      config: {
        api_key: {
          description: "API Key",
          required: true,
          sensitive: true,
          default: null,
        },
      },
      details: {
        name: "test-config",
        authentication: {
          api_key: "test-key",
        },
      },
      id: "test-provider",
      display_name: "Test Provider",
      can_query: false,
      can_notify: false,
      tags: [],
      validatedScopes: {},
      pulling_available: false,
      pulling_enabled: true,
      categories: ["Others"],
      coming_soon: false,
      health: false,
      installed: true,
      linked: true,
      last_alert_received: "",
    },
  ];

  const mockDefinition: Definition = {
    sequence: [],
    properties: {
      id: "test-workflow",
      name: "Test Workflow",
      description: "Test Description",
      disabled: false,
      isLocked: false,
      consts: {},
    },
  };

  it("should validate a task step with valid configuration", () => {
    const step: V2Step = {
      id: "test-step",
      name: "Test Step",
      componentType: "task",
      type: "step-test",
      properties: {
        config: "test-config",
        with: {
          param1: "value1",
        },
        actionParams: [],
        stepParams: [],
      },
    };

    const result = validateStepPure(
      step,
      mockProviders,
      mockInstalledProviders,
      mockDefinition
    );
    expect(result).toEqual([]);
  });

  it("should validate a switch step with valid conditions", () => {
    const step: V2Step = {
      id: "test-switch",
      name: "Test Switch",
      componentType: "switch",
      type: "condition-threshold",
      properties: {
        value: "100",
        compare_to: "200",
      },
      branches: {
        true: [
          {
            id: "action1",
            name: "Action 1",
            componentType: "task",
            type: "action-test",
            properties: {
              actionParams: [],
              stepParams: [],
            },
          },
        ],
        false: [],
      },
    };

    const result = validateStepPure(
      step,
      mockProviders,
      mockInstalledProviders,
      mockDefinition
    );
    expect(result).toEqual([]);
  });

  it("should validate a foreach step with valid configuration", () => {
    const step: V2Step = {
      id: "test-foreach",
      name: "Test Foreach",
      componentType: "container",
      type: "foreach",
      properties: {
        value: "{{ alert.items }}",
      },
      sequence: [],
    };

    const result = validateStepPure(
      step,
      mockProviders,
      mockInstalledProviders,
      mockDefinition
    );
    expect(result).toEqual([]);
  });

  it("should detect missing provider configuration", () => {
    const step: V2Step = {
      id: "test-step",
      name: "Test Step",
      componentType: "task",
      type: "step-test",
      properties: {
        config: "",
        with: {
          param1: "value1",
        },
        actionParams: [],
        stepParams: [],
      },
    };

    const result = validateStepPure(
      step,
      mockProviders,
      mockInstalledProviders,
      mockDefinition
    );
    expect(result).toEqual([["No test provider selected", "warning"]]);
  });

  it("should detect uninstalled provider", () => {
    const step: V2Step = {
      id: "test-step",
      name: "Test Step",
      componentType: "task",
      type: "step-test",
      properties: {
        config: "uninstalled-config",
        with: {
          param1: "value1",
        },
        actionParams: [],
        stepParams: [],
      },
    };

    const result = validateStepPure(
      step,
      mockProviders,
      mockInstalledProviders,
      mockDefinition
    );
    expect(result).toEqual([
      [
        "The 'uninstalled-config' test provider is not installed. Please install it before executing this workflow.",
        "warning",
      ],
    ]);
  });
});

describe("validateGlobalPure", () => {
  it("should validate a complete workflow definition", () => {
    const definition: Definition = {
      properties: {
        id: "test-workflow",
        name: "Test Workflow",
        description: "Test Description",
        disabled: false,
        isLocked: false,
        consts: {},
        alert: {
          service: "test-service",
        },
      },
      sequence: [
        {
          id: "step1",
          name: "Test Step",
          componentType: "task",
          type: "step-test",
          properties: {
            actionParams: [],
            stepParams: [],
          },
        },
      ],
    };

    const result = validateGlobalPure(definition);
    expect(result).toHaveLength(0);
  });

  it("should detect missing workflow name", () => {
    const definition: Definition = {
      properties: {
        id: "test-workflow",
        name: "",
        description: "Test Description",
        disabled: false,
        isLocked: false,
        consts: {},
      },
      sequence: [],
    };

    const result = validateGlobalPure(definition);
    expect(result).toContainEqual([
      "workflow_name",
      "Workflow name cannot be empty.",
    ]);
  });

  it("should detect missing workflow description", () => {
    const definition: Definition = {
      properties: {
        id: "test-workflow",
        name: "Test Workflow",
        description: "",
        disabled: false,
        isLocked: false,
        consts: {},
      },
      sequence: [],
    };

    const result = validateGlobalPure(definition);
    expect(result).toContainEqual([
      "workflow_description",
      "Workflow description cannot be empty.",
    ]);
  });

  it("should detect missing triggers", () => {
    const definition: Definition = {
      properties: {
        id: "test-workflow",
        name: "Test Workflow",
        description: "Test Description",
        disabled: false,
        isLocked: false,
        consts: {},
      },
      sequence: [],
    };

    const result = validateGlobalPure(definition);
    expect(result).toContainEqual([
      "trigger_start",
      "Workflow should have at least one trigger.",
    ]);
  });

  it("should detect empty interval trigger", () => {
    const definition: Definition = {
      properties: {
        id: "test-workflow",
        name: "Test Workflow",
        description: "Test Description",
        disabled: false,
        isLocked: false,
        consts: {},
        interval: "",
      },
      sequence: [],
    };

    const result = validateGlobalPure(definition);
    expect(result).toContainEqual([
      "interval",
      "Workflow interval cannot be empty.",
    ]);
  });

  it("should detect empty alert trigger", () => {
    const definition: Definition = {
      properties: {
        id: "test-workflow",
        name: "Test Workflow",
        description: "Test Description",
        disabled: false,
        isLocked: false,
        consts: {},
        alert: {},
      },
      sequence: [],
    };

    const result = validateGlobalPure(definition);
    expect(result).toContainEqual([
      "alert",
      "Alert trigger should have at least one filter.",
    ]);
  });

  it("should detect empty incident trigger", () => {
    const definition: Definition = {
      properties: {
        id: "test-workflow",
        name: "Test Workflow",
        description: "Test Description",
        disabled: false,
        isLocked: false,
        consts: {},
        incident: {
          events: [],
        },
      },
      sequence: [
        {
          id: "step1",
          name: "Test Step",
          componentType: "task",
          type: "step-test",
          properties: {
            actionParams: [],
            stepParams: [],
          },
        },
      ],
    };

    const result = validateGlobalPure(definition);
    expect(result).toContainEqual([
      "incident",
      "Workflow incident trigger cannot be empty.",
    ]);
  });

  it("should detect missing steps", () => {
    const definition: Definition = {
      properties: {
        id: "test-workflow",
        name: "Test Workflow",
        description: "Test Description",
        disabled: false,
        isLocked: false,
        consts: {},
        alert: {
          service: "test-service",
        },
      },
      sequence: [],
    };

    const result = validateGlobalPure(definition);
    expect(result).toContainEqual([
      "trigger_end",
      "At least one step or action is required.",
    ]);
  });
});
