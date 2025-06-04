/**
 * @fileoverview
 * Validates a mustache variable name in a UI builder, it's slightly different from the YAML validator because UI builder has a different structure, like nested steps, etc.
 * TODO: refactor to share code with the YAML validator
 */

import { V2Step, Definition } from "../model/types";
import { ALLOWED_MUSTACHE_VARIABLE_REGEX, MUSTACHE_REGEX } from "./mustache";

type V2StepWithParentId = V2Step & { parentId?: string };

/*
 * Validates a mustache variable name in a UI builder.
 *
 * @param cleanedVariableName - Mustache variable name without curly brackets.
 * @param currentStep - The current step in the sequence in workflow-store format (V2Step + {parentId: string} for loops)
 * @param definition - The definition of the workflow in workflow-store format.
 * @param secrets - The secrets of the workflow. This is used to validate secrets.
 * @returns An error message if the variable name is invalid, otherwise null.
 */
export const validateMustacheVariableForUIBuilderStep = (
  cleanedVariableName: string,
  _currentStep: V2Step,
  definition: Definition,
  secrets: Record<string, string>
): string | null => {
  const flatSequence = flattenSequence(definition.sequence);
  const currentStep = flatSequence.find(
    (step) => step.name === _currentStep.name || step.id === _currentStep.id
  );
  if (!currentStep) {
    // wtf exception, should never happen
    throw new Error("Current step not found in the sequence");
  }
  if (!cleanedVariableName) {
    return "Empty mustache variable.";
  }
  if (cleanedVariableName === ".") {
    if (currentStep.parentId) {
      return null;
    }
    return `Variable: '${cleanedVariableName}' - needs to be used in a for loop.`;
  }
  if (!ALLOWED_MUSTACHE_VARIABLE_REGEX.test(cleanedVariableName)) {
    if (
      cleanedVariableName.includes("[") ||
      cleanedVariableName.includes("]")
    ) {
      return `Variable: '${cleanedVariableName}' - bracket notation is not supported, use dot notation instead.`;
    }
    return `Variable: '${cleanedVariableName}' - contains invalid characters.`;
  }
  const parts = cleanedVariableName.split(".");
  if (!parts.every((part) => part.length > 0)) {
    return `Variable: '${cleanedVariableName}' - Parts cannot be empty.`;
  }
  if (parts[0] === "foreach") {
    if (currentStep.parentId) {
      return null;
    }
    return `Variable: '${cleanedVariableName}' - 'foreach' can only be used in a step with foreach.`;
  }
  if (parts[0] === "value") {
    if (currentStep.parentId) {
      return null;
    }
    return `Variable: '${cleanedVariableName}' - 'value' can only be used in a step with foreach.`;
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
      return `Variable: '${cleanedVariableName}' - To access a secret, you need to specify the secret name.`;
    }
    if (!secrets[secretName]) {
      return `Variable: '${cleanedVariableName}' - Secret '${secretName}' not found.`;
    }
    return null;
  }
  if (parts[0] === "vars") {
    const varName = parts?.[1];
    if (!varName) {
      return `Variable: '${cleanedVariableName}' - To access a variable, you need to specify the variable name.`;
    }
    if (
      currentStep.componentType !== "task" ||
      !currentStep.properties.vars?.[varName]
    ) {
      return `Variable: '${cleanedVariableName}' - Variable '${varName}' not found in step definition.`;
    }
    return null;
  }
  if (parts[0] === "consts") {
    const constName = parts[1];
    if (!constName) {
      return `Variable: '${cleanedVariableName}' - To access a constant, you need to specify the constant name.`;
    }
    if (!definition.properties.consts?.[constName]) {
      return `Variable: '${cleanedVariableName}' - Constant '${constName}' not found.`;
    }
    return null;
  }
  if (parts[0] === "steps") {
    const stepName = parts[1];
    if (!stepName) {
      return `Variable: '${cleanedVariableName}' - To access the results of a step, you need to specify the step name.`;
    }
    // todo: check if
    // - the step exists
    // - it's not the current step (can't access own results, only enrich_alert and enrich_incident can access their own results)
    // - it's above the current step
    // - if it's a step it cannot access actions since they run after steps
    const step = flatSequence.find(
      (step) => step.id === stepName || step.name === stepName
    );
    const stepIndex = flatSequence.findIndex(
      (step) => step.id === stepName || step.name === stepName
    );
    const currentStepIndex = flatSequence.findIndex(
      (step) => step.id === currentStep.id
    );
    if (!step) {
      return `Variable: '${cleanedVariableName}' - a '${stepName}' step doesn't exist.`;
    }
    const isCurrentStep = step.id === currentStep.id;
    if (isCurrentStep) {
      return `Variable: '${cleanedVariableName}' - You can't access the results of the current step.`;
    }
    if (stepIndex > currentStepIndex) {
      return `Variable: '${cleanedVariableName}' - You can't access the results of a step that appears after the current step.`;
    }
    if (
      currentStep.type.startsWith("step-") &&
      step.type.startsWith("action-")
    ) {
      return `Variable: '${cleanedVariableName}' - You can't access the results of an action from a step.`;
    }

    if (parts.length > 2 && parts[2] === "results") {
      // todo: validate results properties
      return null;
    } else {
      return `Variable: '${cleanedVariableName}' - To access the results of a step, use 'results' as suffix.`;
    }
  }
  if (parts[0] === "inputs") {
    const inputName = parts?.[1];
    if (!inputName) {
      return `Variable: '${cleanedVariableName}' - To access an input, you need to specify the input name.`;
    }
    if (!definition.properties.inputs?.find((i) => i.name === inputName)) {
      return `Variable: '${cleanedVariableName}' - Input '${inputName}' not defined. ${
        definition.properties.inputs?.length
          ? `Available inputs: ${definition.properties.inputs.map((i) => i.name).join(", ")}`
          : "Define inputs in the workflow definition under 'inputs'."
      }`;
    }
    return null;
  }
  return `Variable: '${cleanedVariableName}' - unknown variable.`;
};

function flattenSequence(
  sequence: V2Step[],
  parentId?: string
): V2StepWithParentId[] {
  const flatSequence: V2StepWithParentId[] = [];
  for (const step of sequence) {
    const stepWithParentId = { ...step, parentId };
    if (step.componentType === "container") {
      flatSequence.push(stepWithParentId);
      flatSequence.push(...flattenSequence(step.sequence || [], step.id));
    } else {
      flatSequence.push(stepWithParentId);
    }
  }
  return flatSequence;
}

/**
 * Validates all mustache variables in a string.
 *
 * @param string - The string to validate.
 * @param currentStep - The current step in the sequence in workflow-store format.
 * @param definition - The definition of the workflow in workflow-store format.
 * @param secrets - The secrets of the workflow. This is used to validate secrets.
 * @returns An array of error messages if the variable names are invalid, otherwise an empty array.
 */
export const validateAllMustacheVariablesForUIBuilderStep = (
  string: string,
  currentStep: V2Step,
  definition: Definition,
  secrets: Record<string, string>
) => {
  const matches = [...string.matchAll(MUSTACHE_REGEX)];
  if (!matches) {
    return [];
  }
  const errors: string[] = [];
  matches.forEach((matchExecArray) => {
    const match = matchExecArray[1];
    const error = validateMustacheVariableForUIBuilderStep(
      match,
      currentStep,
      definition,
      secrets
    );
    if (error) {
      errors.push(error);
    }
  });
  return errors;
};
