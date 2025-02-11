import { Definition, V2Step } from "@/app/(keep)/workflows/builder/types";

export function globalValidatorV2(
  definition: Definition,
  setGlobalValidationError: (id: string | null, error: string | null) => void
): boolean {
  const workflowName = definition?.properties?.name;
  const workflowDescription = definition?.properties?.description;
  if (!workflowName) {
    setGlobalValidationError(null, "Workflow name cannot be empty.");
    return false;
  }
  if (!workflowDescription) {
    setGlobalValidationError(null, "Workflow description cannot be empty.");
    return false;
  }

  if (
    !!definition?.properties &&
    !definition.properties["manual"] &&
    !definition.properties["interval"] &&
    !definition.properties["alert"] &&
    !definition.properties["incident"]
  ) {
    setGlobalValidationError(
      "trigger_start",
      "Workflow should have at least one trigger."
    );
    return false;
  }

  if (
    definition?.properties &&
    "interval" in definition.properties &&
    !definition.properties.interval
  ) {
    setGlobalValidationError("interval", "Workflow interval cannot be empty.");
    return false;
  }

  const alertSources = Object.values(definition.properties.alert || {}).filter(
    Boolean
  );
  if (
    definition?.properties &&
    definition.properties["alert"] &&
    alertSources.length == 0
  ) {
    setGlobalValidationError(
      "alert",
      "Workflow alert trigger cannot be empty."
    );
    return false;
  }

  const incidentActions = Object.values(
    definition.properties.incident || {}
  ).filter(Boolean);
  if (
    definition?.properties &&
    definition.properties["incident"] &&
    incidentActions.length == 0
  ) {
    setGlobalValidationError(
      "incident",
      "Workflow incident trigger cannot be empty."
    );
    return false;
  }

  const anyStepOrAction = definition?.sequence?.length > 0;
  if (!anyStepOrAction) {
    setGlobalValidationError(null, "At least 1 step/action is required.");
  }
  const anyActionsInMainSequence = (
    definition.sequence[0] as V2Step
  )?.sequence?.some((step) => step?.type?.includes("action-"));
  if (anyActionsInMainSequence) {
    // This checks to see if there's any steps after the first action
    const actionIndex = (
      definition?.sequence?.[0] as V2Step
    )?.sequence?.findIndex((step) => step.type.includes("action-"));
    if (actionIndex && definition?.sequence) {
      const sequence = definition?.sequence?.[0]?.sequence || [];
      for (let i = actionIndex + 1; i < sequence.length; i++) {
        if (sequence[i]?.type?.includes("step-")) {
          setGlobalValidationError(
            sequence[i].id,
            "Steps cannot be placed after actions."
          );
          return false;
        }
      }
    }
  }
  const valid = anyStepOrAction;
  if (valid) setGlobalValidationError(null, null);
  return valid;
}

export function validateGlobalPure(
  definition: Definition
): [string, string] | null {
  const workflowName = definition?.properties?.name;
  const workflowDescription = definition?.properties?.description;
  if (!workflowName) {
    return ["workflow_name", "Workflow name cannot be empty."];
  }
  if (!workflowDescription) {
    return ["workflow_description", "Workflow description cannot be empty."];
  }

  if (
    !!definition?.properties &&
    !definition.properties["manual"] &&
    !definition.properties["interval"] &&
    !definition.properties["alert"] &&
    !definition.properties["incident"]
  ) {
    return ["trigger_start", "Workflow should have at least one trigger."];
  }

  if (
    definition?.properties &&
    "interval" in definition.properties &&
    !definition.properties.interval
  ) {
    return ["interval", "Workflow interval cannot be empty."];
  }

  const alertSources = Object.values(definition.properties.alert || {}).filter(
    Boolean
  );
  if (
    definition?.properties &&
    definition.properties["alert"] &&
    alertSources.length == 0
  ) {
    return ["alert", "Workflow alert trigger cannot be empty."];
  }

  const incidentActions = Object.values(
    definition.properties.incident || {}
  ).filter(Boolean);
  if (
    definition?.properties &&
    definition.properties["incident"] &&
    incidentActions.length == 0
  ) {
    return ["incident", "Workflow incident trigger cannot be empty."];
  }

  const anyStepOrAction = definition?.sequence?.length > 0;
  if (!anyStepOrAction) {
    return ["workflow_name", "At least 1 step/action is required."];
  }
  const anyActionsInMainSequence = (
    definition.sequence[0] as V2Step
  )?.sequence?.some((step) => step?.type?.includes("action-"));
  if (anyActionsInMainSequence) {
    // This checks to see if there's any steps after the first action
    const actionIndex = (
      definition?.sequence?.[0] as V2Step
    )?.sequence?.findIndex((step) => step.type.includes("action-"));
    if (actionIndex && definition?.sequence) {
      const sequence = definition?.sequence?.[0]?.sequence || [];
      for (let i = actionIndex + 1; i < sequence.length; i++) {
        if (sequence[i]?.type?.includes("step-")) {
          return [sequence[i].id, "Steps cannot be placed after actions."];
        }
      }
    }
  }
  return null;
}

export function stepValidatorV2(
  step: V2Step,
  setStepValidationError: (step: V2Step, error: string | null) => void
): boolean {
  if (step.type.includes("condition-")) {
    if (!step.name) {
      setStepValidationError(step, "Step/action name cannot be empty.");
      return false;
    }
    const branches = (step?.branches || {
      true: [],
      false: [],
    }) as V2Step["branches"];
    const onlyActions = branches?.true?.every((step: V2Step) =>
      step.type.includes("action-")
    );
    if (!onlyActions) {
      setStepValidationError(step, "Conditions can only contain actions.");
      return false;
    }
    const conditionHasActions = branches?.true
      ? branches?.true.length > 0
      : false;
    if (!conditionHasActions)
      setStepValidationError(
        step,
        "Conditions must contain at least one action."
      );
    const valid = conditionHasActions && onlyActions;
    if (valid) setStepValidationError(step, null);
    return valid;
  }
  if (step?.componentType === "task") {
    const valid = step?.name !== "";
    if (!valid) setStepValidationError(step, "Step name cannot be empty.");
    if (!step?.properties?.with) {
      setStepValidationError(
        step,
        "There is step/action with no parameters configured!"
      );
      return false;
    }
    if (valid && step?.properties?.with) {
      setStepValidationError(step, null);
    }
    return valid;
  }
  setStepValidationError(step, null);
  return true;
}

export function validateStepPure(step: V2Step): string | null {
  if (step.type.includes("condition-")) {
    if (!step.name) {
      return "Step/action name cannot be empty.";
    }
    const branches = (step?.branches || {
      true: [],
      false: [],
    }) as V2Step["branches"];
    const onlyActions = branches?.true?.every((step: V2Step) =>
      step.type.includes("action-")
    );
    if (!onlyActions) {
      return "Conditions can only contain actions.";
    }
    const conditionHasActions = branches?.true
      ? branches?.true.length > 0
      : false;
    if (!conditionHasActions) {
      return "Conditions must contain at least one action.";
    }
    const valid = conditionHasActions && onlyActions;
    return valid ? null : "Conditions must contain at least one action.";
  }
  if (step?.componentType === "task") {
    if (!step?.name) {
      return "Step name cannot be empty.";
    }
    if (
      !Object.values(step?.properties?.with || {}).some(
        (value) => String(value).length > 0
      )
    ) {
      return "Step/action with no parameters configured!";
    }
    return null;
  }
  return null;
}
