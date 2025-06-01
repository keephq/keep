import { validateStepPure, validateGlobalPure } from "../validate-definition";
import { Provider } from "@/shared/api/providers";
import { Definition, V2Step } from "../../model/types";

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

  const mockSecrets = {};

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
      mockSecrets,
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
      mockSecrets,
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
      mockSecrets,
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
      mockSecrets,
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
      mockSecrets,
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
