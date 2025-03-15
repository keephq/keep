import { Provider } from "@/shared/api/providers";
import { Definition, V2Step } from "./types";
import { getWithParams } from "../lib/parser";

export type ValidationResult = [string, string];
export type ValidationError = [string, "error" | "warning"];
/**
 * Extracts the trimmed value from mustache syntax by removing curly brackets.
 *
 * @param mustacheString - A string containing mustache syntax like "{{ variable }}"
 * @returns The trimmed inner value without curly brackets
 */
function extractMustacheValue(mustacheString: string): string {
  // Use regex to match content between {{ and }} and trim whitespace
  const match = mustacheString.match(/\{\{\s*(.*?)\s*\}\}/);

  // Return the captured group if found, otherwise return empty string
  return match ? match[1] : "";
}

export const validateMustacheVariableName = (
  variableName: string,
  currentStep: V2Step,
  definition: Definition
) => {
  const cleanedVariableName = extractMustacheValue(variableName);
  const parts = cleanedVariableName.split(".");
  if (!parts.every((part) => part.length > 0)) {
    return `Variable: '${variableName}' - Parts cannot be empty.`;
  }
  if (parts[0] === "alert") {
    // todo: validate alert properties
    return null;
  }
  if (parts[0] === "incident") {
    // todo: validate incident properties
    return null;
  }
  if (parts[0] === "steps") {
    const stepName = parts[1];
    if (!stepName) {
      return `Variable: '${variableName}' - To access the results of a step, you need to specify the step name.`;
    }
    // todo: check if
    // - the step exists
    // - it's not the current step (can't access own results, only enrich_alert and enrich_incident can access their own results)
    // - it's above the current step
    // - if it's a step it cannot access actions since they run after steps
    const step = definition.sequence.find(
      (step) => step.id === stepName || step.name === stepName
    );
    const stepIndex = definition.sequence.findIndex(
      (step) => step.id === stepName || step.name === stepName
    );
    const currentStepIndex = definition.sequence.findIndex(
      (step) => step.id === currentStep.id
    );
    if (!step) {
      return `Variable: '${variableName}' - a '${stepName}' step that doesn't exist.`;
    }
    const isCurrentStep = step.id === currentStep.id;
    if (isCurrentStep) {
      return `Variable: '${variableName}' - You can't access the results of the current step.`;
    }
    if (stepIndex > currentStepIndex) {
      return `Variable: '${variableName}' - You can't access the results of a step that appears after the current step.`;
    }
    if (
      currentStep.type.startsWith("step-") &&
      step.type.startsWith("action-")
    ) {
      return `Variable: '${variableName}' - You can't access the results of an action from a step.`;
    }

    if (!definition.sequence?.some((step) => step.name === stepName)) {
      return `Variable: '${variableName}' - a '${stepName}' step that doesn't exist.`;
    }
    if (parts[2] === "results") {
      // todo: validate results properties
      return null;
    } else {
      return `Variable: '${variableName}' - To access the results of a step, use 'results' as suffix.`;
    }
  }
  return null;
};

export const validateAllMustacheVariablesInString = (
  string: string,
  currentStep: V2Step,
  definition: Definition
) => {
  const regex = /\{\{([^}]+)\}\}/g;
  const matches = string.match(regex);
  if (!matches) {
    return [];
  }
  const errors: string[] = [];
  matches.forEach((match) => {
    const error = validateMustacheVariableName(match, currentStep, definition);
    if (error) {
      errors.push(error);
    }
  });
  return errors;
};

export const checkProviderNeedsInstallation = (providerObject: Provider) => {
  return providerObject.config && Object.keys(providerObject.config).length > 0;
};

export function validateGlobalPure(definition: Definition): ValidationResult[] {
  const errors: ValidationResult[] = [];
  const workflowName = definition?.properties?.name;
  const workflowDescription = definition?.properties?.description;
  if (!workflowName) {
    errors.push(["workflow_name", "Workflow name cannot be empty."]);
  }
  if (!workflowDescription) {
    errors.push([
      "workflow_description",
      "Workflow description cannot be empty.",
    ]);
  }

  if (
    !!definition?.properties &&
    !definition.properties["manual"] &&
    !definition.properties["interval"] &&
    !definition.properties["alert"] &&
    !definition.properties["incident"]
  ) {
    errors.push([
      "trigger_start",
      "Workflow should have at least one trigger.",
    ]);
  }

  if (
    definition?.properties &&
    "interval" in definition.properties &&
    !definition.properties.interval
  ) {
    errors.push(["interval", "Workflow interval cannot be empty."]);
  }

  const alertSources = Object.values(definition.properties.alert || {}).filter(
    Boolean
  );
  if (
    definition?.properties &&
    definition.properties["alert"] &&
    alertSources.length == 0
  ) {
    errors.push(["alert", "Alert trigger should have at least one filter."]);
  }

  const incidentEvents = definition.properties.incident?.events;
  if (
    definition?.properties &&
    definition.properties["incident"] &&
    incidentEvents?.length == 0
  ) {
    errors.push(["incident", "Workflow incident trigger cannot be empty."]);
  }

  const anyStepOrAction = definition?.sequence?.length > 0;
  if (!anyStepOrAction) {
    errors.push(["trigger_end", "At least one step or action is required."]);
  }
  const firstStep = definition?.sequence?.[0];
  const firstStepSequence =
    firstStep?.componentType === "container" ? firstStep.sequence : [];
  const anyActionsInMainSequence = firstStepSequence?.some((step) =>
    step?.type?.includes("action-")
  );
  if (anyActionsInMainSequence) {
    // This checks to see if there's any steps after the first action
    const actionIndex = firstStepSequence?.findIndex((step) =>
      step.type.includes("action-")
    );
    if (actionIndex && definition?.sequence) {
      const sequence = firstStepSequence;
      for (let i = actionIndex + 1; i < sequence.length; i++) {
        if (sequence[i]?.type?.includes("step-")) {
          errors.push([
            sequence[i].id,
            "Steps cannot be placed after actions.",
          ]);
        }
      }
    }
  }
  return errors;
}

function validateProviderConfig(
  providerType: string | undefined,
  providerConfig: string,
  providers: Provider[],
  installedProviders: Provider[]
) {
  const providerObject = providers?.find((p) => p.type === providerType);

  if (!providerObject) {
    return `Provider type '${providerType}' is not supported`;
  }
  // If config is not empty, it means that the provider needs installation
  const doesProviderNeedInstallation =
    checkProviderNeedsInstallation(providerObject);

  if (!doesProviderNeedInstallation) {
    return null;
  }

  if (!providerConfig) {
    return `No ${providerType} provider selected`;
  }

  if (
    doesProviderNeedInstallation &&
    installedProviders.find(
      (p) => p.type === providerType && p.details?.name === providerConfig
    ) === undefined
  ) {
    return `The '${providerConfig}' ${providerType} provider is not installed. Please install it before executing this workflow.`;
  }
  return null;
}

export function validateStepPure(
  step: V2Step,
  providers: Provider[],
  installedProviders: Provider[],
  definition: Definition
): ValidationError[] {
  const validationErrors: ValidationError[] = [];
  // todo: validate `enrich_alert` and `enrich_incident`
  if (
    (step.componentType === "task" || step.componentType === "container") &&
    step.properties.if
  ) {
    const variableErrors = validateAllMustacheVariablesInString(
      step.properties.if,
      step,
      definition
    );
    variableErrors.forEach((error) => {
      validationErrors.push([error, "warning"]);
    });
  }
  if (step.componentType === "switch") {
    if (!step.name) {
      validationErrors.push(["Condition name cannot be empty.", "error"]);
    }
    if (step.type === "condition-threshold") {
      if (!step.properties.value) {
        validationErrors.push(["Condition value cannot be empty.", "error"]);
      }
      const variableErrorsValue = validateAllMustacheVariablesInString(
        step.properties.value,
        step,
        definition
      );
      variableErrorsValue.forEach((error) => {
        validationErrors.push([error, "warning"]);
      });
      if (!step.properties.compare_to) {
        validationErrors.push([
          "Condition compare to cannot be empty.",
          "error",
        ]);
      }
      const variableErrorsCompareTo = validateAllMustacheVariablesInString(
        step.properties.compare_to,
        step,
        definition
      );
      variableErrorsCompareTo.forEach((error) => {
        validationErrors.push([error, "warning"]);
      });
    }
    if (step.type === "condition-assert") {
      if (!step.properties.assert) {
        validationErrors.push(["Condition assert cannot be empty.", "error"]);
      }
      const variableErrors = validateAllMustacheVariablesInString(
        step.properties.assert,
        step,
        definition
      );
      variableErrors.forEach((error) => {
        validationErrors.push([error, "warning"]);
      });
    }
    const branches = step.branches || {
      true: [],
      false: [],
    };
    const conditionHasActions = branches.true.length > 0;
    if (!conditionHasActions) {
      validationErrors.push([
        "Conditions true branch must contain at least one step or action.",
        "error",
      ]);
    }
  }
  if (step.componentType === "task") {
    if (!step.name) {
      validationErrors.push(["Step name cannot be empty.", "error"]);
    }
    const providerType = step.type.split("-")[1];
    const providerConfig = (step.properties.config || "").trim();
    const providerError = validateProviderConfig(
      providerType,
      providerConfig,
      providers,
      installedProviders
    );
    if (providerError) {
      validationErrors.push([providerError, "warning"]);
    }
    const withParams = getWithParams(step);
    const isAnyParamConfigured = Object.values(withParams || {}).some(
      (value) => String(value).length > 0
    );
    if (!isAnyParamConfigured) {
      validationErrors.push(["No parameters configured", "error"]);
    }
    for (const [key, value] of Object.entries(withParams)) {
      if (typeof value === "string") {
        const variableErrors = validateAllMustacheVariablesInString(
          value,
          step,
          definition
        );
        variableErrors.forEach((error) => {
          validationErrors.push([error, "warning"]);
        });
      }
    }
  }
  if (step.componentType === "container" && step.type === "foreach") {
    if (!step.properties.value) {
      validationErrors.push(["Foreach value cannot be empty.", "error"]);
    }
    const variableErrors = validateAllMustacheVariablesInString(
      step.properties.value,
      step,
      definition
    );
    variableErrors.forEach((error) => {
      validationErrors.push([error, "warning"]);
    });
  }
  return validationErrors;
}
