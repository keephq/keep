import { Dispatch, SetStateAction } from "react";
import {
  Definition,
  SequentialStep,
  Step,
  BranchedStep,
  Sequence,
} from "sequential-workflow-designer";

export function globalValidator(
  definition: Definition,
  setGlobalValidationError: Dispatch<SetStateAction<string | null>>
): boolean {
  const onlyOneAlert = definition.sequence.length === 1;
  if (!onlyOneAlert) setGlobalValidationError("Only one alert is allowed.");
  const anyActionsInMainSequence = (
    definition.sequence[0] as SequentialStep
  )?.sequence?.some((step) => step.type.includes("action-"));
  if (anyActionsInMainSequence) {
    // This checks to see if there's any steps after the first action
    const actionIndex = (
      definition.sequence[0] as SequentialStep
    )?.sequence.findIndex((step) => step.type.includes("action-"));
    for (
      let i = actionIndex + 1;
      i < (definition.sequence[0] as SequentialStep)?.sequence.length;
      i++
    ) {
      if (
        (definition.sequence[0] as SequentialStep)?.sequence[i].type.includes(
          "step-"
        )
      ) {
        setGlobalValidationError("Cannot have steps after actions.");
        return false;
      }
    }
  }
  const valid = onlyOneAlert;
  if (valid) setGlobalValidationError(null);
  return valid;
}

export function stepValidator(
  step: Step | BranchedStep,
  parentSequence: Sequence,
  definition: Definition,
  setStepValidationError: Dispatch<SetStateAction<string | null>>
): boolean {
  if (step.type === "foreach") {
    // This checks if there's any step that is not action in foreach
    const foreachIncludesNotCondition = (step as SequentialStep).sequence.some(
      (step) => !step.type.includes("condition-")
    );
    if (foreachIncludesNotCondition) {
      setStepValidationError("Foreach can only contain conditions.");
      return false;
    }
  }
  if (step.type.includes("condition-")) {
    const onlyActions = (step as BranchedStep).branches.true.every((step) =>
      step.type.includes("action-")
    );
    if (!onlyActions) {
      setStepValidationError("Conditions can only contain actions.");
      return false;
    }
    const conditionHasActions = (step as BranchedStep).branches.true.length > 0;
    if (!conditionHasActions)
      setStepValidationError("Conditions must contain at least one action.");
    const valid = conditionHasActions && onlyActions;
    if (valid) setStepValidationError(null);
    return valid;
  }
  if (step.componentType === "task") {
    const valid = step.name !== "";
    if (!valid) setStepValidationError("Step name cannot be empty.");
    if (valid) setStepValidationError(null);
    return valid;
  }
  return true;
}
