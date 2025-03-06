import { Provider } from "@/shared/api/providers";
import { Definition, V2Step } from "./types";

export type ValidationResult = [string, string];

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

  const incidentActions = Object.values(
    definition.properties.incident || {}
  ).filter(Boolean);
  if (
    definition?.properties &&
    definition.properties["incident"] &&
    incidentActions.length == 0
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
  installedProviders: Provider[]
): string | null {
  if (step.componentType === "switch") {
    if (!step.name) {
      return "Condition name cannot be empty.";
    }
    if (step.type === "condition-threshold") {
      if (!step.properties.value) {
        return "Condition value cannot be empty.";
      }
      if (!step.properties.compare_to) {
        return "Condition compare to cannot be empty.";
      }
    }
    if (step.type === "condition-assert") {
      if (!step.properties.assert) {
        return "Condition assert cannot be empty.";
      }
    }
    const branches = step.branches || {
      true: [],
      false: [],
    };
    const conditionHasActions = branches.true.length > 0;
    if (!conditionHasActions) {
      return "Conditions true branch must contain at least one step or action.";
    }
    return null;
  }
  if (step.componentType === "task") {
    if (!step.name) {
      return "Step name cannot be empty.";
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
      return providerError;
    }
    if (
      !Object.values(step?.properties?.with || {}).some(
        (value) => String(value).length > 0
      )
    ) {
      return "No parameters configured";
    }
    return null;
  }
  if (step.componentType === "container" && step.type === "foreach") {
    if (!step.properties.value) {
      return "Foreach value cannot be empty.";
    }
  }
  return null;
}
