import {
  Definition as FlowDefinition,
  ReactFlowDefinition,
  V2Step,
} from "@/app/(keep)/workflows/builder/types";

export interface ValidationResult {
  isValid: boolean;
  error?: {
    nodeId: string | null;
    message: string;
  };
}

export function globalValidatorV2(
  definition: FlowDefinition
): ValidationResult {
  const workflowName = definition?.properties?.name;
  const workflowDescription = definition?.properties?.description;

  if (!workflowName) {
    return {
      isValid: false,
      error: { nodeId: null, message: "Workflow name cannot be empty." },
    };
  }
  if (!workflowDescription) {
    return {
      isValid: false,
      error: {
        nodeId: null,
        message: "Workflow description cannot be empty.",
      },
    };
  }

  if (
    !!definition?.properties &&
    !definition.properties["manual"] &&
    !definition.properties["interval"] &&
    !definition.properties["alert"] &&
    !definition.properties["incident"]
  ) {
    return {
      isValid: false,
      error: {
        nodeId: "trigger_start",
        message: "Workflow should have at least one trigger.",
      },
    };
  }

  if (
    definition?.properties &&
    "interval" in definition.properties &&
    !definition.properties.interval
  ) {
    return {
      isValid: false,
      error: {
        nodeId: "interval",
        message: "Workflow interval cannot be empty.",
      },
    };
  }

  const alertSources = Object.values(definition.properties.alert || {}).filter(
    Boolean
  );
  if (
    definition?.properties &&
    definition.properties["alert"] &&
    alertSources.length == 0
  ) {
    return {
      isValid: false,
      error: {
        nodeId: "alert",
        message: "Workflow alert trigger cannot be empty.",
      },
    };
  }

  const incidentActions = Object.values(
    definition.properties.incident || {}
  ).filter(Boolean);
  if (
    definition?.properties &&
    definition.properties["incident"] &&
    incidentActions.length == 0
  ) {
    return {
      isValid: false,
      error: {
        nodeId: "incident",
        message: "Workflow incident trigger cannot be empty.",
      },
    };
  }

  const anyStepOrAction = definition?.sequence?.length > 0;
  if (!anyStepOrAction) {
    return {
      isValid: false,
      error: { nodeId: null, message: "At least 1 step/action is required." },
    };
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
          return {
            isValid: false,
            error: {
              nodeId: sequence[i].id,
              message: "Steps cannot be placed after actions.",
            },
          };
        }
      }
    }
  }
  const valid = anyStepOrAction;
  if (valid) return { isValid: true };
  return { isValid: false };
}

export function stepValidatorV2(
  step: V2Step,
  parentSequence?: V2Step,
  definition?: ReactFlowDefinition
): ValidationResult {
  if (step.type.includes("condition-")) {
    if (!step.name) {
      return {
        isValid: false,
        error: {
          nodeId: step.id,
          message: "Step/action name cannot be empty.",
        },
      };
    }
    const branches = (step?.branches || {
      true: [],
      false: [],
    }) as V2Step["branches"];
    const onlyActions = branches?.true?.every((step: V2Step) =>
      step.type.includes("action-")
    );
    if (!onlyActions) {
      return {
        isValid: false,
        error: {
          nodeId: step.id,
          message: "Conditions can only contain actions.",
        },
      };
    }
    const conditionHasActions = branches?.true
      ? branches?.true.length > 0
      : false;
    if (!conditionHasActions)
      return {
        isValid: false,
        error: {
          nodeId: step.id,
          message: "Conditions must contain at least one action.",
        },
      };
    const valid = conditionHasActions && onlyActions;
    if (valid) return { isValid: true };
    return { isValid: false };
  }
  if (step?.componentType === "task") {
    const valid = step?.name !== "";
    if (!valid)
      return {
        isValid: false,
        error: { nodeId: step.id, message: "Step name cannot be empty." },
      };
    if (!Object.keys(step?.properties?.with || {}).length) {
      return {
        isValid: false,
        error: {
          nodeId: step.id,
          message: `The step has no parameters configured!`,
        },
      };
    }
    if (valid && Object.keys(step?.properties?.with || {}).length) {
      return { isValid: true };
    }
    return { isValid: false };
  }
  return { isValid: true };
}
