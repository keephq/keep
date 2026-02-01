/**
 * Workflow Definition Parser Module
 *
 * This module handles bidirectional conversion between:
 * 1. YAML workflow definitions (human-readable format used for storage)
 * 2. Internal workflow definition objects (used for UI rendering and manipulation)
 *
 * Key responsibilities:
 * - Parse YAML workflow definitions into structured Definition objects
 * - Convert workflow Definition objects back to YAML format
 * - Handle complex workflow components like:
 *   - Steps and Actions with provider configurations
 *   - Conditional logic (assert/threshold conditions)
 *   - Foreach loops
 *   - Triggers and failure handlers
 * - Extract and validate workflow inputs
 * - Generate unique IDs for workflow components
 *
 * The module maintains type safety throughout the conversion process while
 * preserving all workflow properties, conditions, and relationships.
 */

import {
  Definition,
  DefinitionV2,
  V2ActionStep,
  V2Step,
  V2StepConditionAssert,
  V2StepConditionThreshold,
  V2StepForeach,
  V2StepStep,
} from "@/entities/workflows";
import { Provider } from "@/shared/api/providers";
import { v4 as uuidv4 } from "uuid";
import {
  YamlAssertCondition,
  YamlStepOrAction,
  YamlThresholdCondition,
  WorkflowInput,
  YamlWorkflowDefinition,
} from "@/entities/workflows/model/yaml.types";
import { parseWorkflowYamlStringToJSON } from "./yaml-utils";

type StepOrActionWithType = YamlStepOrAction & { type: "step" | "action" };

function getV2StepOrV2Action(
  actionOrStep: StepOrActionWithType,
  providers?: Provider[]
): V2StepStep | V2ActionStep {
  /**
   * Generate a step or action definition (both are kinda the same)
   */
  const providerType = actionOrStep.provider?.type;
  const provider = providers?.find((p) => p.type === providerType);
  return {
    id: actionOrStep?.id || uuidv4(),
    name: actionOrStep.name,
    componentType: "task",
    type: `${actionOrStep.type}-${providerType}`,
    properties: {
      config: (actionOrStep.provider?.config as string)
        ?.replaceAll("{{", "")
        .replaceAll("}}", "")
        .replaceAll("providers.", ""),
      with: actionOrStep.provider?.with,
      stepParams: provider?.query_params!,
      actionParams: provider?.notify_params!,
      if: actionOrStep.if,
      vars: actionOrStep.vars,
      "on-failure": actionOrStep?.["on-failure"],
    },
  };
}

function getV2Foreach(
  actionOrStep: StepOrActionWithType & { foreach: string },
  providers?: Provider[],
  sequenceStep?:
    | V2StepStep
    | V2ActionStep
    | V2StepConditionAssert
    | V2StepConditionThreshold
  // TODO: support multiple sequence steps
): V2StepForeach {
  return {
    id: actionOrStep?.id || uuidv4(),
    type: "foreach",
    componentType: "container",
    name: "Foreach",
    properties: {
      value: actionOrStep.foreach,
    },
    sequence: [sequenceStep ?? getV2StepOrV2Action(actionOrStep, providers)],
  };
}

function getV2Condition(
  condition: YamlAssertCondition | YamlThresholdCondition,
  action: StepOrActionWithType,
  providers?: Provider[]
): V2StepConditionThreshold | V2StepConditionAssert {
  const generatedConditionStep =
    condition.type === "threshold"
      ? {
          id: condition.id || uuidv4(),
          name: condition.name,
          type: "condition-threshold" as const,
          componentType: "switch" as const,
          alias: condition.alias,
          properties: {
            value: condition.value,
            compare_to: condition.compare_to,
          },
          branches: {
            true: [getV2StepOrV2Action(action, providers)],
            false: [],
          },
        }
      : {
          id: condition.id || uuidv4(),
          name: condition.name,
          type: "condition-assert" as const,
          componentType: "switch" as const,
          alias: condition.alias,
          properties: {
            assert: (condition as YamlAssertCondition).assert,
          },
          branches: {
            true: [getV2StepOrV2Action(action, providers)],
            false: [],
          },
        };

  return generatedConditionStep;
}

export function getWorkflowDefinition(
  workflowId: string,
  name: string,
  description: string,
  disabled: boolean,
  consts: Record<string, string>,
  steps: V2Step[],
  conditions: V2Step[],
  triggers: { [key: string]: { [key: string]: string } } = {},
  inputs: WorkflowInput[] = [],
  onFailure?: V2ActionStep
): Definition {
  /**
   * Generate the workflow definition
   */

  return {
    sequence: [...steps, ...conditions],
    properties: {
      id: workflowId,
      name: name,
      description: description,
      disabled: disabled,
      isLocked: true,
      consts: consts,
      inputs: inputs,
      "on-failure": onFailure,
      ...triggers,
    },
  };
}

// For steps, we have 2 types of data representations for the same data
// 1. YamlStepOrAction, YamlAssertCondition, YamlThresholdCondition: json from yaml
// 2. V2StepStep, V2ActionStep, V2StepConditionAssert, V2StepConditionThreshold: a bit different json for working with on frontend

// The flow of parseWorkflow() is as follows:
// 1. Parse the yaml file to get YamlStepOrAction, YamlAssertCondition, YamlThresholdCondition
// 2. Convert YamlStepOrAction, YamlAssertCondition, YamlThresholdCondition to V2StepStep, V2ActionStep, V2StepConditionAssert, V2StepConditionThreshold

// TODO: use zod to validate the input, use yaml as a source of truth
export function parseWorkflow(
  workflowString: string,
  providers: Provider[]
): Definition {
  /**
   * Parse the alert file and generate the definition
   */
  const parsedWorkflowFile = parseWorkflowYamlStringToJSON(workflowString);
  // This is to support both old and new structure of workflow
  const workflow = parsedWorkflowFile.alert
    ? parsedWorkflowFile.alert
    : parsedWorkflowFile.workflow;
  const steps: V2Step[] = [];

  const workflowSteps =
    workflow.steps?.map((s: YamlStepOrAction) => ({ ...s, type: "step" })) ||
    [];
  const workflowActions =
    workflow.actions?.map((a: YamlStepOrAction) => ({
      ...a,
      type: "action",
    })) || [];
  const conditions: (V2StepConditionThreshold | V2StepConditionAssert)[] = [];

  const workflowStepsAndActions: StepOrActionWithType[] = [
    ...workflowSteps,
    ...workflowActions,
  ];

  workflowStepsAndActions.forEach((action) => {
    // This means this action always runs, there's no condition and no alias
    if (!action.condition && !action.if && !action.foreach) {
      steps.push(getV2StepOrV2Action(action, providers));
    } else if (action.if) {
      // If this is an alias, we need to find the existing condition and add this action to it
      const cleanIf = action.if.replace("{{", "").replace("}}", "").trim();
      const existingCondition = conditions.find((a) => a.alias === cleanIf);
      if (existingCondition) {
        existingCondition.branches.true.push(
          getV2StepOrV2Action(action, providers)
        );
      } else {
        if (action.foreach) {
          steps.push(
            getV2Foreach(
              action as StepOrActionWithType & { foreach: string },
              providers
            )
          );
        } else {
          steps.push(getV2StepOrV2Action(action, providers));
        }
      }
    } else if (action.foreach) {
      steps.push(
        getV2Foreach(
          action as StepOrActionWithType & { foreach: string },
          providers
        )
      );
    } else if (action.condition) {
      action.condition.forEach((condition) => {
        conditions.push(getV2Condition(condition, action, providers));
      });
    }
  });

  const triggers =
    workflow.triggers?.reduce((prev: any, curr: any) => {
      const currType = curr.type;
      let value = curr.value;
      if (currType === "alert") {
        value = {};
        if (curr.filters) {
          const filters = curr.filters.reduce((prev: any, curr: any) => {
            prev[curr.key] = curr.value;
            return prev;
          }, {});
          value["filters"] = filters;
        }
        if (curr.cel) {
          value["cel"] = curr.cel;
        }
        if (curr.only_on_change) {
          value["only_on_change"] = curr.only_on_change;
        }
      } else if (currType === "manual") {
        value = "true";
      } else if (currType === "incident") {
        value = { events: curr.events };
      }
      prev[currType] = value;
      return prev;
    }, {}) || {};

  const onFailure = workflow["on-failure"]
    ? (getV2StepOrV2Action(
        { ...workflow["on-failure"], type: "action" },
        providers
      ) as V2ActionStep)
    : undefined;

  return getWorkflowDefinition(
    workflow.id,
    workflow.name,
    workflow.description,
    workflow.disabled,
    workflow.consts,
    steps,
    conditions,
    triggers,
    workflow?.inputs ?? [],
    onFailure
  );
}

export function getWithParams(
  s: V2ActionStep | V2StepStep
): Record<string, string | number | boolean | object> {
  if (!s) {
    return {};
  }
  s.properties = s.properties || {};
  const withParams =
    (s.properties.with as {
      [key: string]: string | number | boolean | object;
    }) ?? {};
  if (withParams) {
    Object.keys(withParams).forEach((key) => {
      try {
        // Don't parse code, it's a string. E.g. python-step with code='{"a": "b"}' should stay a string
        if (key === "code") {
          withParams[key] = withParams[key] as string;
          return;
        }
        const withParamValue = withParams[key] as string;
        const withParamJson = JSON.parse(withParamValue);
        withParams[key] = withParamJson;
      } catch {}
    });
  }
  return withParams;
}

export function getYamlConditionFromStep(
  condition: V2StepConditionThreshold | V2StepConditionAssert
) {
  return condition.type === "condition-threshold"
    ? ({
        name: condition.name,
        type: "threshold" as const,
        alias: condition.alias,
        value: condition.properties.value,
        compare_to: condition.properties.compare_to,
      } as YamlThresholdCondition)
    : ({
        name: condition.name,
        type: "assert" as const,
        alias: condition.alias,
        assert: condition.properties.assert,
      } as YamlAssertCondition);
}

function getActionsFromCondition(
  condition: V2StepConditionThreshold | V2StepConditionAssert,
  foreach?: string
): { actions: YamlStepOrAction[]; steps: YamlStepOrAction[] } {
  // TODO: refactor this to be more readable
  // TODO: should we create alias if it doesn't exist? and if so, should we restrict user from setting 'if' if action is in condition already?
  const steps: (V2StepStep | V2ActionStep)[] = condition?.branches?.true || [];
  const compiledActions: YamlStepOrAction[] = [];
  const compiledSteps: YamlStepOrAction[] = [];
  let isConditionInsertedStep = false;
  let isConditionInsertedAction = false;
  const alias =
    condition.alias || (steps.length > 1 ? condition.name : undefined);
  const conditionWithAlias = alias ? { ...condition, alias } : condition;
  steps.forEach((a) => {
    if (a.type.startsWith("step-")) {
      const ifParam =
        alias && isConditionInsertedStep ? `{{ ${alias} }}` : a.properties.if;
      const shouldInsertCondition =
        !alias || (!!alias && !isConditionInsertedStep);
      const compiledAction = getYamlStepFromStep(
        { ...a, properties: { ...a.properties, if: ifParam } } as V2StepStep,
        {
          condition: shouldInsertCondition ? conditionWithAlias : undefined,
          foreach,
        }
      );
      compiledSteps.push(compiledAction);
      isConditionInsertedStep =
        isConditionInsertedStep || shouldInsertCondition;
    } else {
      const ifParam =
        alias && isConditionInsertedAction ? `{{ ${alias} }}` : a.properties.if;
      const shouldInsertCondition =
        !alias || (!!alias && !isConditionInsertedAction);
      const compiledAction = getYamlActionFromAction(
        { ...a, properties: { ...a.properties, if: ifParam } } as V2ActionStep,
        {
          condition: shouldInsertCondition ? conditionWithAlias : undefined,
          foreach,
        }
      );
      compiledActions.push(compiledAction);
      isConditionInsertedAction =
        isConditionInsertedAction || shouldInsertCondition;
    }
  });
  return {
    actions: compiledActions,
    steps: compiledSteps,
  };
}

export function getYamlStepFromStep(
  s: V2StepStep,
  {
    condition,
    foreach,
  }: {
    condition?: V2StepConditionThreshold | V2StepConditionAssert;
    foreach?: string;
  } = {}
): YamlStepOrAction {
  const withParams = getWithParams(s);
  const providerType = s.type.replace("step-", "");
  const providerName =
    (s.properties.config as string)?.trim() || `default-${providerType}`;
  const provider: YamlStepOrAction["provider"] = {
    type: s.type.replace("step-", ""),
    config: `{{ providers.${providerName} }}`,
    with: withParams,
  };
  const ifParam =
    typeof s.properties.if === "string" && s.properties.if.trim() !== ""
      ? s.properties.if
      : undefined;
  const step: YamlStepOrAction = {
    name: s.name,
    foreach: foreach ? foreach : undefined,
    if: ifParam,
    condition: condition ? [getYamlConditionFromStep(condition)] : undefined,
    provider: provider,
    "on-failure": s.properties["on-failure"],
  };
  if (s.properties.vars) {
    step.vars = s.properties.vars;
  }
  return step;
}

export function getYamlActionFromAction(
  s: V2ActionStep,
  {
    condition,
    foreach,
  }: {
    condition?: V2StepConditionThreshold | V2StepConditionAssert;
    foreach?: string;
  } = {}
): YamlStepOrAction {
  const withParams = getWithParams(s);
  const providerType = s.type.replace("action-", "");
  const providerName =
    (s.properties.config as string)?.trim() || `default-${providerType}`;
  const provider: YamlStepOrAction["provider"] = {
    type: s.type.replace("action-", ""),
    config: `{{ providers.${providerName} }}`,
    with: withParams,
  };
  const ifParam =
    typeof s.properties.if === "string" && s.properties.if.trim() !== ""
      ? s.properties.if
      : undefined;
  const action: YamlStepOrAction = {
    name: s.name,
    foreach: foreach ? foreach : undefined,
    if: ifParam,
    condition: condition ? [getYamlConditionFromStep(condition)] : undefined,
    provider: provider,
    "on-failure": s.properties["on-failure"],
  };
  if (s.properties.vars) {
    action.vars = s.properties.vars;
  }
  return action;
}

/**
 * Convert the definition to a YamlWorkflowDefinition to be used in serializing
 */
export function getYamlWorkflowDefinition(
  definition: Definition
): YamlWorkflowDefinition["workflow"] {
  const alert = definition;
  const alertId = alert.properties.id as string;
  const name = (alert.properties.name as string) ?? "";
  const description = (alert.properties.description as string) ?? "";
  const disabled = alert.properties.disabled ?? false;
  const owners = (alert.properties.owners as string[]) ?? [];
  const services = (alert.properties.services as string[]) ?? [];
  const consts = (alert.properties.consts as Record<string, string>) ?? {};

  let steps: YamlStepOrAction[] = [];
  let actions: YamlStepOrAction[] = [];

  for (const step of alert.sequence) {
    if (step.type === "foreach" && step.componentType === "container") {
      const forEach = step as V2StepForeach;
      const forEachValue = forEach.properties.value as string;
      const condition = forEach.sequence.find(
        (step): step is V2StepConditionThreshold | V2StepConditionAssert =>
          step.type === "condition-assert" ||
          step.type === "condition-threshold"
      );
      if (condition) {
        const { actions: conditionActions, steps: conditionSteps } =
          getActionsFromCondition(condition, forEachValue);
        actions = [...actions, ...conditionActions];
        steps = [...steps, ...conditionSteps];
      } else {
        const forEachSequence = forEach?.sequence || [];
        const stepOrAction = forEachSequence[0] as V2StepStep | V2ActionStep;
        if (!stepOrAction) {
          continue;
        }
        if (stepOrAction.type.startsWith("action-")) {
          actions.push(
            getYamlActionFromAction(stepOrAction as V2ActionStep, {
              foreach: forEachValue,
            })
          );
        } else {
          steps.push(
            getYamlStepFromStep(stepOrAction as V2StepStep, {
              foreach: forEachValue,
            })
          );
        }
      }
    } else if (
      step.type === "condition-assert" ||
      step.type === "condition-threshold"
    ) {
      const { actions: conditionActions, steps: conditionSteps } =
        getActionsFromCondition(
          step as V2StepConditionThreshold | V2StepConditionAssert
        );
      actions = [...actions, ...conditionActions];
      steps = [...steps, ...conditionSteps];
    } else if (step.type.startsWith("step-")) {
      steps.push(getYamlStepFromStep(step as V2StepStep));
    } else if (step.type.startsWith("action-")) {
      actions.push(getYamlActionFromAction(step as V2ActionStep));
    }
  }

  const triggers = [];
  if (alert.properties.manual === "true") triggers.push({ type: "manual" });
  if (alert.properties.alert) {
    const alertTrigger: any = { type: "alert" };
    if (alert.properties.alert.filters) {
      const filters = Object.keys(alert.properties.alert.filters).map((key) => {
        return {
          key: key,
          value: (alert.properties.alert as any)[key],
        };
      });
      alertTrigger["filters"] = filters;
    }
    if (alert.properties.alert.cel) {
      alertTrigger["cel"] = alert.properties.alert.cel;
    }
    if (alert.properties.alert.only_on_change) {
      alertTrigger["only_on_change"] = alert.properties.alert.only_on_change;
    }
    triggers.push(alertTrigger);
  }
  if (alert.properties.interval) {
    triggers.push({
      type: "interval",
      value: alert.properties.interval,
    });
  }
  if (alert.properties.incident) {
    triggers.push({
      type: "incident",
      events: alert.properties.incident.events,
    });
  }
  const onFailure = alert.properties["on-failure"]
    ? {
        ...getYamlActionFromAction({
          ...alert.properties["on-failure"],
          id: "on-failure",
          name: "on-failure",
        }),
        // name is not needed for on-failure, but it's produced by getYamlActionFromAction, so we need to remove it
        name: undefined,
      }
    : undefined;
  return {
    id: alertId,
    name: name,
    description: description,
    disabled: Boolean(disabled),
    triggers: triggers,
    inputs: alert.properties.inputs,
    owners: owners,
    services: services,
    consts: consts,
    steps: steps,
    actions: actions,
    "on-failure": onFailure,
  };
}

export function wrapDefinitionV2({
  properties,
  sequence,
  isValid,
}: Definition): DefinitionV2 {
  return {
    value: {
      sequence: sequence,
      properties: properties,
    },
    isValid: !!isValid,
  };
}

export function extractWorkflowInputs(workflowYaml: string): WorkflowInput[] {
  const parsedWorkflow = parseWorkflowYamlStringToJSON(workflowYaml);
  const inputs =
    parsedWorkflow?.inputs || parsedWorkflow?.workflow?.inputs || [];

  // Add visual indicator of required status for inputs without defaults
  const enhancedInputs = inputs.map((input: WorkflowInput) => {
    // Mark inputs without defaults as visually required
    if (input.default === undefined && !input.required) {
      return { ...input, visuallyRequired: true };
    }
    return input;
  });
  return enhancedInputs;
}
