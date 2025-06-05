import { Provider } from "@/shared/api/providers";
import { Definition, V2Step } from "../model/types";
import { getWithParams } from "./parser";
import { validateAllMustacheVariablesForUIBuilderStep } from "./validate-mustache-ui-builder";

export type ValidationResult = [string, string];
export type ValidationError = [string, "error" | "warning" | "info"];

export const checkProviderNeedsInstallation = (
  providerObject: Pick<Provider, "type" | "config">
) => {
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
  if (providerType === "mock") {
    // Mock provider is always installed and doesn't need configuration
    return null;
  }

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
  secrets: Record<string, string>,
  definition: Definition
): ValidationError[] {
  const validationErrors: ValidationError[] = [];
  // todo: validate `enrich_alert` and `enrich_incident` shape
  if (
    (step.componentType === "task" || step.componentType === "container") &&
    step.properties.if
  ) {
    const variableErrors = validateAllMustacheVariablesForUIBuilderStep(
      step.properties.if,
      step,
      definition,
      secrets
    );
    variableErrors.forEach((error) => {
      validationErrors.push([error, "error"]);
    });
  }
  if (step.componentType === "task" && step.properties.with?.enrich_alert) {
    const values = step.properties.with.enrich_alert.map((item) => item.value);
    const variableErrors = validateAllMustacheVariablesForUIBuilderStep(
      values.join(","),
      step,
      definition,
      secrets
    );
    variableErrors.forEach((error) => {
      validationErrors.push([error, "error"]);
    });
  }
  if (step.componentType === "task" && step.properties.with?.enrich_incident) {
    const values = step.properties.with.enrich_incident.map(
      (item) => item.value
    );
    const variableErrors = validateAllMustacheVariablesForUIBuilderStep(
      values.join(","),
      step,
      definition,
      secrets
    );
    variableErrors.forEach((error) => {
      validationErrors.push([error, "error"]);
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
      const variableErrorsValue = validateAllMustacheVariablesForUIBuilderStep(
        step.properties.value?.toString() ?? "",
        step,
        definition,
        secrets
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
      const variableErrorsCompareTo =
        validateAllMustacheVariablesForUIBuilderStep(
          step.properties.compare_to?.toString() ?? "",
          step,
          definition,
          secrets
        );
      variableErrorsCompareTo.forEach((error) => {
        validationErrors.push([error, "error"]);
      });
    }
    if (step.type === "condition-assert") {
      if (!step.properties.assert) {
        validationErrors.push(["Condition assert cannot be empty.", "error"]);
      }
      const variableErrors = validateAllMustacheVariablesForUIBuilderStep(
        step.properties.assert,
        step,
        definition,
        secrets
      );
      variableErrors.forEach((error) => {
        validationErrors.push([error, "error"]);
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
        const variableErrors = validateAllMustacheVariablesForUIBuilderStep(
          value,
          step,
          definition,
          secrets
        );
        variableErrors.forEach((error) => {
          validationErrors.push([error, "error"]);
        });
      }
    }
  }
  if (step.componentType === "container" && step.type === "foreach") {
    if (!step.properties.value) {
      validationErrors.push(["Foreach value cannot be empty.", "error"]);
    }
    const variableErrors = validateAllMustacheVariablesForUIBuilderStep(
      step.properties.value,
      step,
      definition,
      secrets
    );
    variableErrors.forEach((error) => {
      validationErrors.push([error, "error"]);
    });
  }
  return validationErrors;
}
