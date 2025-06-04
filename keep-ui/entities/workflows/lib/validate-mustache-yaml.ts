/**
 * @fileoverview
 * Validates a mustache variable name in a YAML workflow definition.
 * TODO: refactor to share code with the UI builder validator
 */

import { YamlStepOrAction, YamlWorkflowDefinition } from "../model/yaml.types";
import { Provider } from "@/shared/api/providers";
import { ALLOWED_MUSTACHE_VARIABLE_REGEX } from "./mustache";
import { checkProviderNeedsInstallation } from "./validate-definition";

/**
 * Validates a mustache variable name in a YAML workflow definition.
 *
 * @param cleanedVariableName - Mustache variable name without curly brackets.
 * @param currentStep - The current step in the sequence in YAML format.
 * @param currentStepType - The type of the current step.
 * @param definition - The definition of the workflow in YAML format.
 * @param secrets - The secrets of the workflow. This is used to validate secrets.
 * @param providers - The providers of the workflow. This is used to validate providers.
 * @param installedProviders - The installed providers of the workflow. This is used to validate installed providers.
 * @returns An [error message, "error" | "warning" | "info"] if the variable name is invalid, otherwise null.
 */
export const validateMustacheVariableForYAMLStep = (
  cleanedVariableName: string,
  currentStep: YamlStepOrAction,
  currentStepType: "step" | "action",
  definition: YamlWorkflowDefinition["workflow"],
  secrets: Record<string, string>,
  providers: Provider[] | null,
  installedProviders: Provider[] | null
): [string, "error" | "warning" | "info"] | null => {
  if (!cleanedVariableName) {
    return ["Empty mustache variable.", "warning"];
  }
  if (cleanedVariableName === ".") {
    if (currentStep.foreach) {
      return null;
    }
    return [
      `Variable: '${cleanedVariableName}' - short syntax can only be used in a step with foreach.`,
      "warning",
    ];
  }
  if (!ALLOWED_MUSTACHE_VARIABLE_REGEX.test(cleanedVariableName)) {
    if (
      cleanedVariableName.includes("[") ||
      cleanedVariableName.includes("]")
    ) {
      return [
        `Variable: '${cleanedVariableName}' - bracket notation is not supported, use dot notation instead.`,
        "warning",
      ];
    }
    return [
      `Variable: '${cleanedVariableName}' - contains invalid characters.`,
      "warning",
    ];
  }
  const parts = cleanedVariableName.split(".");
  if (!parts.every((part) => part.length > 0)) {
    return [
      `Variable: '${cleanedVariableName}' - path parts cannot be empty.`,
      "warning",
    ];
  }
  if (parts[0] === "foreach") {
    if (currentStep.foreach) {
      return null;
    }
    return [
      `Variable: '${cleanedVariableName}' - 'foreach' can only be used in a step with foreach.`,
      "warning",
    ];
  }
  if (parts[0] === "value") {
    if (currentStep.foreach) {
      return null;
    }
    return [
      `Variable: '${cleanedVariableName}' - 'value' can only be used in a step with foreach.`,
      "warning",
    ];
  }
  if (parts[0] === "providers") {
    const providerName = parts[1];
    if (!providerName) {
      return [
        `Variable: '${cleanedVariableName}' - To access a provider, you need to specify the provider name.`,
        "warning",
      ];
    }
    if (!providers || !installedProviders) {
      // Skip validation if providers or installedProviders are not available
      return null;
    }
    const isDefault = providerName.startsWith("default-");
    if (isDefault) {
      const providerType = isDefault ? providerName.split("-")[1] : null;
      const provider = providers.find((p) => p.type === providerType);
      if (!provider) {
        return [
          `Variable: '${cleanedVariableName}' - Unknown provider type '${providerType}'.`,
          "warning",
        ];
      }
      const doesProviderNeedInstallation =
        checkProviderNeedsInstallation(provider);
      const installedProvider = installedProviders.find(
        (p) => p.details.name === providerName
      );
      if (doesProviderNeedInstallation && !installedProvider) {
        const providerType = currentStep.provider.type;
        const availableProvidersOfType = installedProviders.filter(
          (p) => p.type === providerType
        );
        return [
          `Variable: '${cleanedVariableName}' - Provider '${providerName}' is not installed.${
            availableProvidersOfType.length > 0
              ? ` Available '${providerType}' providers: ${availableProvidersOfType.map((p) => p.details.name).join(", ")}`
              : ""
          }`,
          "warning",
        ];
      }
    } else {
      const provider = installedProviders.find(
        (p) => p.details.name === providerName
      );
      if (!provider) {
        const providerType = currentStep.provider.type;
        const availableProvidersOfType = installedProviders.filter(
          (p) => p.type === providerType
        );
        return [
          `Variable: '${cleanedVariableName}' - Provider '${providerName}' is not installed.${
            availableProvidersOfType.length > 0
              ? ` Available '${providerType}' providers: ${availableProvidersOfType.map((p) => p.details.name).join(", ")}`
              : ""
          }`,
          "warning",
        ];
      }
    }
    return null;
  }
  if (parts[0] === "alert") {
    // todo: validate alert properties
    return null;
  }
  if (parts[0] === "incident") {
    // todo: validate incident properties
    return null;
  }
  if (parts[0] === "secrets") {
    const secretName = parts[1];
    if (!secretName) {
      return [
        `Variable: '${cleanedVariableName}' - To access a secret, you need to specify the secret name.`,
        "warning",
      ];
    }
    if (!secrets[secretName]) {
      return [
        `Variable: '${cleanedVariableName}' - Secret '${secretName}' not found.`,
        "error",
      ];
    }
    return null;
  }
  if (parts[0] === "vars") {
    const varName = parts?.[1];
    if (!varName) {
      return [
        `Variable: '${cleanedVariableName}' - To access a variable, you need to specify the variable name.`,
        "warning",
      ];
    }
    if (!currentStep.vars?.[varName]) {
      return [
        `Variable: '${cleanedVariableName}' - Variable '${varName}' not found in step definition.`,
        "error",
      ];
    }
    return null;
  }
  if (parts[0] === "consts") {
    const constName = parts[1];
    if (!constName) {
      return [
        `Variable: '${cleanedVariableName}' - To access a constant, you need to specify the constant name.`,
        "warning",
      ];
    }
    if (!definition.consts?.[constName]) {
      return [
        `Variable: '${cleanedVariableName}' - Constant '${constName}' not found.`,
        "error",
      ];
    }
  }
  if (parts[0] === "steps") {
    const stepName = parts[1];
    if (!stepName) {
      return [
        `Variable: '${cleanedVariableName}' - To access the results of a step, you need to specify the step name.`,
        "warning",
      ];
    }
    // todo: check if
    // - the step exists
    // - it's not the current step (can't access own results, only enrich_alert and enrich_incident can access their own results)
    // - it's above the current step
    // - if it's a step it cannot access actions since they run after steps
    const step = definition.steps?.find((s) => s.name === stepName);
    const stepIndex =
      definition.steps?.findIndex((s) => s.name === stepName) ?? -1;
    const currentStepIndex =
      currentStepType === "step"
        ? (definition.steps?.findIndex((s) => s.name === currentStep.name) ??
          -1)
        : -1;
    if (!step || stepIndex === -1) {
      return [
        `Variable: '${cleanedVariableName}' - a '${stepName}' step doesn't exist.`,
        "error",
      ];
    }
    const isCurrentStep = step.name === currentStep.name;
    if (isCurrentStep) {
      return [
        `Variable: '${cleanedVariableName}' - You can't access the results of the current step.`,
        "error",
      ];
    }
    if (currentStepIndex !== -1 && stepIndex > currentStepIndex) {
      return [
        `Variable: '${cleanedVariableName}' - You can't access the results of a step that appears after the current step.`,
        "error",
      ];
    }

    if (!definition.steps?.some((step) => step.name === stepName)) {
      return [
        `Variable: '${cleanedVariableName}' - a '${stepName}' step that doesn't exist.`,
        "error",
      ];
    }
    if (
      parts.length > 2 &&
      (parts[2] === "results" ||
        parts[2].startsWith("results.") ||
        parts[2].startsWith("results["))
    ) {
      // todo: validate results properties
      return null;
    } else {
      return [
        `Variable: '${cleanedVariableName}' - To access the results of a step, use 'results' as suffix.`,
        "warning",
      ];
    }
  }
  return [`Variable: '${cleanedVariableName}' - unknown variable.`, "warning"];
};
