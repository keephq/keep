import { validateMustacheVariableForYAMLStep } from "../validate-mustache-yaml";
import { Provider } from "@/shared/api/providers";
import { YamlWorkflowDefinition } from "../../model/yaml.types";

describe("validateMustacheVariableNameForYAML", () => {
  const stepWithVars = {
    name: "step-with-vars",
    provider: {
      type: "step-test",
      config: "test-config",
      with: {},
    },
    vars: {
      test: "test",
    },
  };
  const stepWithForeach = {
    name: "step-with-foreach",
    foreach: "{{steps.First Step.results}}",
    provider: {
      type: "step-test",
      config: "test-config",
      with: {
        param1: "{{.}}",
      },
    },
  };
  const mockWorkflowDefinition: YamlWorkflowDefinition["workflow"] = {
    id: "test-workflow",
    name: "Test Workflow",
    description: "Test Description",
    consts: {
      test: "test",
    },
    inputs: [
      {
        name: "message",
        description: "The message to log to the console",
        type: "string",
      },
    ],
    triggers: [
      {
        type: "manual",
      },
    ],
    steps: [
      {
        name: "First Step",
        provider: {
          type: "step-test",
          config: "test-config",
          with: {
            param1: "value1",
          },
        },
      },
      {
        name: "Second Step",
        provider: {
          type: "action-test",
          config: "test-config",
          with: {
            param1: "value1",
          },
        },
      },
      stepWithForeach,
      stepWithVars,
    ],
  };

  const mockSecrets: Record<string, string> = {
    API_KEY: "test-key",
  };

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
    {
      type: "notrequiringinstallation",
      config: {},
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
      installed: false,
      linked: false,
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

  it("should detect empty variable name", () => {
    const result = validateMustacheVariableForYAMLStep(
      "",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual(["Empty mustache variable.", "warning"]);
  });

  it("should detect empty path parts", () => {
    const result = validateMustacheVariableForYAMLStep(
      "step..results",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'step..results' - path parts cannot be empty.",
      "warning",
    ]);
  });

  it("should validate alert variables", () => {
    const result = validateMustacheVariableForYAMLStep(
      "alert.name",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should validate incident variables", () => {
    const result = validateMustacheVariableForYAMLStep(
      "incident.title",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should validate valid secrets", () => {
    const result = validateMustacheVariableForYAMLStep(
      "secrets.API_KEY",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should detect missing secret name", () => {
    const result = validateMustacheVariableForYAMLStep(
      "secrets.",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'secrets.' - path parts cannot be empty.",
      "warning",
    ]);
  });

  it("should detect non-existent secret", () => {
    const result = validateMustacheVariableForYAMLStep(
      "secrets.MISSING_KEY",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'secrets.MISSING_KEY' - Secret 'MISSING_KEY' not found.",
      "error",
    ]);
  });

  it("should validate provider access", () => {
    const result = validateMustacheVariableForYAMLStep(
      "providers.test-config",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should validate default provider access", () => {
    const result = validateMustacheVariableForYAMLStep(
      "providers.default-notrequiringinstallation",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should detect missing provider name", () => {
    const result = validateMustacheVariableForYAMLStep(
      "providers.",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'providers.' - path parts cannot be empty.",
      "warning",
    ]);
  });

  it("should detect non-existent default provider", () => {
    const result = validateMustacheVariableForYAMLStep(
      "providers.default-nonexistent",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'providers.default-nonexistent' - Unknown provider type 'nonexistent'.",
      "warning",
    ]);
  });

  it("should detect non-installed provider", () => {
    const result = validateMustacheVariableForYAMLStep(
      "providers.nonexistent-config",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'providers.nonexistent-config' - Provider 'nonexistent-config' is not installed.",
      "warning",
    ]);
  });

  it("should validate step results access", () => {
    const result = validateMustacheVariableForYAMLStep(
      "steps.First Step.results",
      mockWorkflowDefinition!.steps![1],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should detect missing step name", () => {
    const result = validateMustacheVariableForYAMLStep(
      "steps.",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'steps.' - path parts cannot be empty.",
      "warning",
    ]);
  });

  it("should detect non-existent step", () => {
    const result = validateMustacheVariableForYAMLStep(
      "steps.Nonexistent Step.results",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'steps.Nonexistent Step.results' - a 'Nonexistent Step' step doesn't exist.",
      "error",
    ]);
  });

  it("should prevent accessing current step results", () => {
    const result = validateMustacheVariableForYAMLStep(
      "steps.First Step.results",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'steps.First Step.results' - You can't access the results of the current step.",
      "error",
    ]);
  });

  it("should prevent accessing future step results", () => {
    const result = validateMustacheVariableForYAMLStep(
      "steps.Second Step.results",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'steps.Second Step.results' - You can't access the results of a step that appears after the current step.",
      "error",
    ]);
  });

  it("should detect missing results suffix", () => {
    const result = validateMustacheVariableForYAMLStep(
      "steps.First Step.output",
      mockWorkflowDefinition!.steps![1],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'steps.First Step.output' - To access the results of a step, use 'results' as suffix.",
      "warning",
    ]);
  });

  it("should skip provider validation when providers are not available", () => {
    const result = validateMustacheVariableForYAMLStep(
      "providers.test-config",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      null,
      null
    );
    expect(result).toBeNull();
  });

  it("should return an error if bracket notation is used", () => {
    const result = validateMustacheVariableForYAMLStep(
      "steps['python-step'].results",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'steps[\'python-step\'].results' - bracket notation is not supported, use dot notation instead.",
      "warning",
    ]);
  });

  it("should allow {{.}} syntax in steps with foreach", () => {
    const result = validateMustacheVariableForYAMLStep(
      ".",
      mockWorkflowDefinition!.steps![2],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should return an error if {{.}} syntax is used in step without foreach", () => {
    const result = validateMustacheVariableForYAMLStep(
      ".",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: '.' - short syntax can only be used in a step with foreach.",
      "warning",
    ]);
  });

  it("should return an error if foreach or value is used in a step without foreach", () => {
    const result = validateMustacheVariableForYAMLStep(
      "foreach.value",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'foreach.value' - 'foreach' can only be used in a step with foreach.",
      "warning",
    ]);

    const result2 = validateMustacheVariableForYAMLStep(
      "value",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result2).toEqual([
      "Variable: 'value' - 'value' can only be used in a step with foreach.",
      "warning",
    ]);
  });

  it("should validate vars variable", () => {
    const result = validateMustacheVariableForYAMLStep(
      "vars.test",
      stepWithVars,
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should return an error if vars variable is not found", () => {
    const result = validateMustacheVariableForYAMLStep(
      "vars.test",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'vars.test' - Variable 'test' not found in step definition.",
      "error",
    ]);
  });

  it("should validate inputs variable", () => {
    const result = validateMustacheVariableForYAMLStep(
      "inputs.message",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should return an error if inputs variable is not found", () => {
    const result = validateMustacheVariableForYAMLStep(
      "inputs.missing",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'inputs.missing' - Input 'missing' not defined. Available inputs: message",
      "error",
    ]);
  });

  it("should validate consts variable", () => {
    const result = validateMustacheVariableForYAMLStep(
      "consts.test",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should return an error if consts variable is not found", () => {
    const result = validateMustacheVariableForYAMLStep(
      "consts.missing",
      mockWorkflowDefinition!.steps![0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: 'consts.missing' - Constant 'missing' not found.",
      "error",
    ]);
  });
});
