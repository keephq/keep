import { validateMustacheVariableNameForYAML } from "../validate-yaml";
import { Provider } from "@/shared/api/providers";
import { YamlWorkflowDefinition } from "../../model/yaml.types";

describe("validateMustacheVariableNameForYAML", () => {
  const mockWorkflowDefinition: YamlWorkflowDefinition = {
    id: "test-workflow",
    name: "Test Workflow",
    description: "Test Description",
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
    const result = validateMustacheVariableNameForYAML(
      "",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual(["Empty mustache variable.", "warning"]);
  });

  it("should detect empty path parts", () => {
    const result = validateMustacheVariableNameForYAML(
      "step..results",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: step..results - path parts cannot be empty.",
      "warning",
    ]);
  });

  it("should validate alert variables", () => {
    const result = validateMustacheVariableNameForYAML(
      "alert.name",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should validate incident variables", () => {
    const result = validateMustacheVariableNameForYAML(
      "incident.title",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should validate valid secrets", () => {
    const result = validateMustacheVariableNameForYAML(
      "secrets.API_KEY",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should detect missing secret name", () => {
    const result = validateMustacheVariableNameForYAML(
      "secrets.",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: secrets. - path parts cannot be empty.",
      "warning",
    ]);
  });

  it("should detect non-existent secret", () => {
    const result = validateMustacheVariableNameForYAML(
      "secrets.MISSING_KEY",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      'Variable: secrets.MISSING_KEY - Secret "MISSING_KEY" not found.',
      "error",
    ]);
  });

  it("should validate provider access", () => {
    const result = validateMustacheVariableNameForYAML(
      "providers.test-config",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should validate default provider access", () => {
    const result = validateMustacheVariableNameForYAML(
      "providers.default-test",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should detect missing provider name", () => {
    const result = validateMustacheVariableNameForYAML(
      "providers.",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: providers. - path parts cannot be empty.",
      "warning",
    ]);
  });

  it("should detect non-existent default provider", () => {
    const result = validateMustacheVariableNameForYAML(
      "providers.default-nonexistent",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      'Variable: providers.default-nonexistent - Provider "default-nonexistent" not found.',
      "warning",
    ]);
  });

  it("should detect non-installed provider", () => {
    const result = validateMustacheVariableNameForYAML(
      "providers.nonexistent-config",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      'Variable: providers.nonexistent-config - Provider "nonexistent-config" is not installed.',
      "warning",
    ]);
  });

  it("should validate step results access", () => {
    const result = validateMustacheVariableNameForYAML(
      "steps.First Step.results",
      mockWorkflowDefinition.steps[1],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toBeNull();
  });

  it("should detect missing step name", () => {
    const result = validateMustacheVariableNameForYAML(
      "steps.",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: steps. - path parts cannot be empty.",
      "warning",
    ]);
  });

  it("should detect non-existent step", () => {
    const result = validateMustacheVariableNameForYAML(
      "steps.Nonexistent Step.results",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      'Variable: steps.Nonexistent Step.results - a "Nonexistent Step" step doesn\'t exist.',
      "error",
    ]);
  });

  it("should prevent accessing current step results", () => {
    const result = validateMustacheVariableNameForYAML(
      "steps.First Step.results",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: steps.First Step.results - You can't access the results of the current step.",
      "error",
    ]);
  });

  it("should prevent accessing future step results", () => {
    const result = validateMustacheVariableNameForYAML(
      "steps.Second Step.results",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      "Variable: steps.Second Step.results - You can't access the results of a step that appears after the current step.",
      "error",
    ]);
  });

  it("should detect missing results suffix", () => {
    const result = validateMustacheVariableNameForYAML(
      "steps.First Step.output",
      mockWorkflowDefinition.steps[1],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      mockProviders,
      mockInstalledProviders
    );
    expect(result).toEqual([
      'Variable: steps.First Step.output - To access the results of a step, use "results" as suffix.',
      "warning",
    ]);
  });

  it("should skip provider validation when providers are not available", () => {
    const result = validateMustacheVariableNameForYAML(
      "providers.test-config",
      mockWorkflowDefinition.steps[0],
      "step",
      mockWorkflowDefinition,
      mockSecrets,
      null,
      null
    );
    expect(result).toBeNull();
  });
});
