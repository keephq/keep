import { YamlStepOrAction, YamlWorkflowDefinition } from "../model/yaml.types";
import { Provider } from "@/shared/api/providers";

export const validateMustacheVariableNameForYAML = (
  cleanedVariableName: string,
  currentStep: YamlStepOrAction,
  currentStepType: "step" | "action",
  definition: YamlWorkflowDefinition["workflow"],
  secrets: Record<string, string>,
  providers: Provider[] | null,
  installedProviders: Provider[] | null
) => {
  if (!cleanedVariableName) {
    return ["Empty mustache variable.", "warning"];
  }
  const parts = cleanedVariableName.split(".");
  if (!parts.every((part) => part.length > 0)) {
    return [
      `Variable: ${cleanedVariableName} - path parts cannot be empty.`,
      "warning",
    ];
  }
  if (parts[0] === "providers") {
    const providerName = parts[1];
    if (!providerName) {
      return [
        `Variable: ${cleanedVariableName} - To access a provider, you need to specify the provider name.`,
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
          `Variable: ${cleanedVariableName} - Provider "${providerName}" not found.`,
          "warning",
        ];
      }
    } else {
      const provider = installedProviders.find(
        (p) => p.details.name === providerName
      );
      if (!provider) {
        return [
          `Variable: ${cleanedVariableName} - Provider "${providerName}" is not installed.`,
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
        `Variable: ${cleanedVariableName} - To access a secret, you need to specify the secret name.`,
        "warning",
      ];
    }
    if (!secrets[secretName]) {
      return [
        `Variable: ${cleanedVariableName} - Secret "${secretName}" not found.`,
        "error",
      ];
    }
    return null;
  }
  if (parts[0] === "consts") {
    const constName = parts[1];
    if (!constName) {
      return [
        `Variable: ${cleanedVariableName} - To access a constant, you need to specify the constant name.`,
      ];
    }
    if (!definition.consts?.[constName]) {
      return [
        `Variable: ${cleanedVariableName} - Constant "${constName}" not found.`,
        "error",
      ];
    }
  }
  if (parts[0] === "steps") {
    const stepName = parts[1];
    if (!stepName) {
      return [
        `Variable: ${cleanedVariableName} - To access the results of a step, you need to specify the step name.`,
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
        `Variable: ${cleanedVariableName} - a "${stepName}" step doesn't exist.`,
        "error",
      ];
    }
    const isCurrentStep = step.name === currentStep.name;
    if (isCurrentStep) {
      return [
        `Variable: ${cleanedVariableName} - You can't access the results of the current step.`,
        "error",
      ];
    }
    if (currentStepIndex !== -1 && stepIndex > currentStepIndex) {
      return [
        `Variable: ${cleanedVariableName} - You can't access the results of a step that appears after the current step.`,
        "error",
      ];
    }

    if (!definition.steps?.some((step) => step.name === stepName)) {
      return [
        `Variable: ${cleanedVariableName} - a "${stepName}" step that doesn't exist.`,
        "error",
      ];
    }
    if (
      parts[2] === "results" ||
      parts[2].startsWith("results.") ||
      parts[2].startsWith("results[")
    ) {
      // todo: validate results properties
      return null;
    } else {
      return [
        `Variable: ${cleanedVariableName} - To access the results of a step, use "results" as suffix.`,
        "warning",
      ];
    }
  }
  return null;
};
