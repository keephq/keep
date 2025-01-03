import {
  Definition as FlowDefinition,
  ReactFlowDefinition,
  V2Step,
  V2Properties,
} from "@/app/(keep)/workflows/builder/types";
import {
  getSchemaByStepType,
  getWorkflowPropertiesSchema,
} from "./utils";

export function globalValidatorV2(
  definition: FlowDefinition,
  setGlobalValidationError: (
    id: string | null,
    error: Record<string, string> | null
  ) => void
): boolean {
  const properties = definition?.properties;
  const result = getWorkflowPropertiesSchema(properties).safeParse(properties);
  const errors = result?.error?.errors;
  const errorMap =
    errors?.reduce<Record<string, string>>((obj, error) => {
      const path = error.path;
      if (path && path[0] && !obj[path[0]]) {
        obj[path[0]] = error?.message?.toString();
      }
      return obj;
    }, {}) || null;

  if (!result.success && errorMap) {
    switch (true) {
      case "interval" in errorMap:
        setGlobalValidationError("interval", errorMap);
        break;
      case "alert" in errorMap:
        setGlobalValidationError("alert", errorMap);
        break;
      case "incident" in errorMap:
        setGlobalValidationError("incident", errorMap);
        break;
      case "manual" in errorMap:
        setGlobalValidationError("manual", errorMap);
        break;
      default:
        setGlobalValidationError(null, errorMap);
    }
    return false;
  }

  if (
    !!properties &&
    !properties["manual"] &&
    !properties["interval"] &&
    !properties["alert"] &&
    !properties["incident"]
  ) {
    setGlobalValidationError("trigger_start", {
      rule_error: "Workflow Should at least have one trigger.",
    });
    return false;
  }

  const anyStepOrAction = definition?.sequence?.length > 0;
  if (!anyStepOrAction) {
    setGlobalValidationError(null, {
      rule_error: "At least 1 step/action is required.",
    });
    return false;
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
          setGlobalValidationError(sequence[i].id, {
            rule_error: "Steps cannot be placed after actions.",
          });
          return false;
        }
      }
    }
  }
  const valid = anyStepOrAction;
  if (valid) setGlobalValidationError(null, null);
  return valid;
}

export const getUniqueKeysFromStep = (properties: V2Properties) => {
  return [
    ...new Set([
      ...(properties.stepParams || []),
      ...(properties.actionParams || []),
    ]),
  ].filter((val) => val);
};

export const getDefaultWith = (uniqueKeys: string[]) => {
  return (
    uniqueKeys?.reduce<V2Properties>((obj, key) => {
      obj[key] = "";
      return obj;
    }, {}) || {}
  );
};

export function stepValidatorV2(
  step: V2Step,
  setStepValidationError: (
    step: V2Step,
    error: null | Record<string, string>
  ) => void,
  parentSequence?: V2Step,
  definition?: ReactFlowDefinition
): boolean {
  const schema = getSchemaByStepType(step.type);

  if (schema) {
    const unqiuekeys = getUniqueKeysFromStep(step.properties);
    const defaultWith = getDefaultWith(unqiuekeys);
    const result = schema.safeParse({
      ...step,
      //Property keys are temporarily created to ensure proper validation and meaningful error messages.
      properties: {
        ...step.properties,
        with: { ...defaultWith, ...(step.properties.with || {}) },
        config: step.properties.config || "",
      },
    });
    if (!result.success) {
      const errorMap = result.error.errors.reduce<Record<string, string>>(
        (obj, err) => {
          const path = err.path.join(".");
          if (path && !(path in obj)) {
            obj[path] = err.message?.toString();
          }
          return obj;
        },
        {}
      );
      setStepValidationError(step, errorMap);
      return false;
    }
  }

  if (step.type === "foreach") {
    let valid = true;
    const sequences = step.sequence || [];
    console.log("enterign thsi foreach", sequences);

    for (let sequence of sequences) {
      valid = stepValidatorV2(sequence, setStepValidationError);
      if (!valid) {
        return false;
      }
    }
    return valid;
  }

  //TO DO: move this to zod validations
  if (step.type.includes("condition-")) {
    const branches = (step?.branches || {
      true: [],
      false: [],
    }) as V2Step["branches"];

    const trueBranches = branches?.true || [];
    const falseBranches = branches?.false || [];
    const onlyActions = branches?.true?.every((step: V2Step) =>
      step.type.includes("action-")
    );
    if (!onlyActions) {
      setStepValidationError(step, {
        rule_error: "Conditions can only contain actions.",
      });
      return false;
    }

    const conditionHasActions = branches?.true
      ? branches?.true.length > 0
      : false;
    if (!conditionHasActions)
      setStepValidationError(step, {
        rule_error: "Conditions must contain at least one action.",
      });
    let valid = conditionHasActions && onlyActions;
    if (valid) setStepValidationError(step, null);

    for (let branch of trueBranches) {
      valid = stepValidatorV2(branch, setStepValidationError);
      if (!valid) {
        return false;
      }
    }

    for (let branch of falseBranches) {
      valid = stepValidatorV2(branch, setStepValidationError);
      if (!valid) {
        return false;
      }
    }
    return valid;
  }

  if (step?.componentType === "task") {
    if (!step?.properties?.with) {
      setStepValidationError(step, {
        rule_error: "Conditions must contain at least one action.",
      });
      return false;
    }
    if (step?.properties?.with) {
      setStepValidationError(step, null);
    }
    return true;
  }

  setStepValidationError(step, null);
  return true;
}
