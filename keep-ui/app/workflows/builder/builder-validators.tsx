import { Dispatch, SetStateAction } from "react";
import { ReactFlowDefinition, V2Step, Definition as FlowDefinition } from "./builder-store";

export function globalValidatorV2(
  definition: FlowDefinition,
  setGlobalValidationError: Dispatch<SetStateAction<string | null>>
): boolean {
  const workflowName = definition?.properties?.name;
  if(!workflowName) {
    setGlobalValidationError("Workflow name cannot be empty.");
    return false;
  }
  const anyStepOrAction = definition?.sequence?.length > 0;
  if (!anyStepOrAction) {
    setGlobalValidationError(
      "At least 1 step/action is required."
    );
  }
  const anyActionsInMainSequence = (
    definition.sequence[0] as V2Step
  )?.sequence?.some((step) => step?.type?.includes("action-"));
  if (anyActionsInMainSequence) {
    // This checks to see if there's any steps after the first action
    const actionIndex = (
      definition?.sequence?.[0] as V2Step
    )?.sequence?.findIndex((step) => step.type.includes("action-"));
    if(actionIndex && definition?.sequence){
      const sequence = definition?.sequence?.[0]?.sequence || [];
      for (
        let i = actionIndex + 1;
        i < sequence.length;
        i++
      ) {
        if (
          sequence[i]?.type?.includes(
            "step-"
          )
        ) {
          setGlobalValidationError("Steps cannot be placed after actions.");
          return false;
        }
      }
    }
  }
  const valid = anyStepOrAction;
  if (valid) setGlobalValidationError(null);
  return valid;
}

export function stepValidatorV2(
  step: V2Step,
  setStepValidationError: (step:V2Step, error:string|null)=>void,
  parentSequence?: V2Step,
  definition?: ReactFlowDefinition,
): boolean {
  if (step.type.includes("condition-")) {
    if(!step.name) {
      setStepValidationError(step, "Step/action name cannot be empty.");
      return false;
    }
    const branches = (step?.branches || {true:[], false:[]}) as V2Step['branches'];
    const onlyActions = branches?.true?.every((step:V2Step) =>
      step.type.includes("action-")
    );
    if (!onlyActions) {
      setStepValidationError(step, "Conditions can only contain actions.");
      return false;
    }
    const conditionHasActions = branches?.true ? branches?.true.length > 0 : false;
    if (!conditionHasActions)
      setStepValidationError(step, "Conditions must contain at least one action.");
    const valid = conditionHasActions && onlyActions;
    if (valid) setStepValidationError(step, null);
    return valid;
  }
  if (step?.componentType === "task") {
    const valid = step?.name !== "";
    if (!valid) setStepValidationError(step, "Step name cannot be empty.");
    if (!step?.properties?.with){
      setStepValidationError(step, 
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
