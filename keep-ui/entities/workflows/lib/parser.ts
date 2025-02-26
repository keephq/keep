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
import { JSON_SCHEMA, load } from "js-yaml";
import {
  YamlAssertCondition,
  YamlStepOrAction,
  YamlThresholdCondition,
  YamlWorkflowDefinition,
} from "@/entities/workflows/model/yaml.types";

function getActionOrStepObj(
  actionOrStep: YamlStepOrAction,
  type: "action" | "step",
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
    type: `${type}-${providerType}`,
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
    },
  };
}

function generateForeach(
  actionOrStep: YamlStepOrAction & { foreach: string },
  stepType: "step" | "action",
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
    sequence: [
      sequenceStep ?? getActionOrStepObj(actionOrStep, stepType, providers),
    ],
  };
}

function generateCondition(
  condition: YamlAssertCondition | YamlThresholdCondition,
  action: YamlStepOrAction,
  stepType: "step" | "action",
  providers?: Provider[]
): (V2StepConditionThreshold | V2StepConditionAssert) | V2StepForeach {
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
            true: [getActionOrStepObj(action, stepType, providers)],
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
            true: [getActionOrStepObj(action, stepType, providers)],
            false: [],
          },
        };

  // If this is a foreach, we need to add the foreach to the condition
  if (action.foreach) {
    return generateForeach(
      action as YamlStepOrAction & { foreach: string },
      stepType,
      providers,
      generatedConditionStep
    );
  }

  return generatedConditionStep;
}

export function generateWorkflow(
  workflowId: string,
  name: string,
  description: string,
  disabled: boolean,
  consts: Record<string, string>,
  steps: V2Step[],
  conditions: V2Step[],
  triggers: { [key: string]: { [key: string]: string } } = {}
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
      ...triggers,
    },
  };
}

export function loadWorkflowYAML(workflowString: string): Definition {
  return load(workflowString, {
    schema: JSON_SCHEMA,
  }) as any;
}

export function parseWorkflow(
  workflowString: string,
  providers: Provider[]
): Definition {
  /**
   * Parse the alert file and generate the definition
   */
  const parsedWorkflowFile = load(workflowString, {
    schema: JSON_SCHEMA,
  }) as any;
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
  const conditions = [] as any;

  const workflowStepsAndActions: (YamlStepOrAction & {
    type: "step" | "action";
  })[] = [...workflowSteps, ...workflowActions];

  workflowStepsAndActions.forEach((action) => {
    const stepType = action.type === "step" ? "step" : "action";
    // This means this action always runs, there's no condition and no alias
    if (!action.condition && !action.if && !action.foreach) {
      steps.push(getActionOrStepObj(action, stepType, providers));
    } else if (action.if) {
      // If this is an alias, we need to find the existing condition and add this action to it
      const cleanIf = action.if.replace("{{", "").replace("}}", "").trim();
      const existingCondition = conditions.find(
        (a: any) => a.alias === cleanIf
      );
      if (existingCondition) {
        existingCondition.branches.true.push(
          getActionOrStepObj(action, stepType, providers)
        );
      } else {
        if (action.foreach) {
          steps.push(
            generateForeach(
              action as YamlStepOrAction & { foreach: string },
              stepType,
              providers
            )
          );
        } else {
          steps.push(getActionOrStepObj(action, stepType, providers));
        }
      }
    } else if (action.foreach) {
      steps.push(
        generateForeach(
          action as YamlStepOrAction & { foreach: string },
          stepType,
          providers
        )
      );
    } else if (action.condition) {
      action.condition.forEach((condition) => {
        conditions.push(
          generateCondition(condition, action, stepType, providers)
        );
      });
    }
  });

  const triggers =
    workflow.triggers?.reduce((prev: any, curr: any) => {
      const currType = curr.type;
      let value = curr.value;
      if (currType === "alert") {
        if (curr.filters) {
          value = curr.filters.reduce((prev: any, curr: any) => {
            prev[curr.key] = curr.value;
            return prev;
          }, {});
        } else {
          value = {};
        }
      } else if (currType === "manual") {
        value = "true";
      } else if (currType === "incident") {
        value = { events: curr.events };
      }
      prev[currType] = value;
      return prev;
    }, {}) || {};

  return generateWorkflow(
    workflow.id,
    workflow.name,
    workflow.description,
    workflow.disabled,
    workflow.consts,
    steps,
    conditions,
    triggers
  );
}

function getWithParams(s: V2ActionStep | V2StepStep): any {
  if (!s) {
    return;
  }
  s.properties = s.properties || {};
  const withParams =
    (s.properties.with as {
      [key: string]: string | number | boolean | object;
    }) ?? {};
  if (withParams) {
    Object.keys(withParams).forEach((key) => {
      try {
        const withParamValue = withParams[key] as string;
        const withParamJson = JSON.parse(withParamValue);
        withParams[key] = withParamJson;
      } catch {}
    });
  }
  return withParams;
}

function getActionsFromCondition(
  condition: V2StepConditionThreshold | V2StepConditionAssert,
  foreach?: string
): YamlStepOrAction[] {
  const compiledCondition =
    condition.type === "condition-threshold"
      ? {
          name: condition.name,
          type: "threshold" as const,
          value: condition.properties.value,
          compare_to: condition.properties.compare_to,
        }
      : {
          name: condition.name,
          type: "assert" as const,
          assert: condition.properties.assert,
        };
  const steps = condition?.branches?.true || ([] as V2Step[]);
  const compiledActions = steps.map((a) => {
    const withParams = getWithParams(a);
    const providerType = a?.type?.replace("action-", "");
    const providerName =
      (a?.properties?.config as string)?.trim() || `default-${providerType}`;
    const provider = {
      type: a.type.replace("action-", ""),
      config: `{{ providers.${providerName} }}`,
      with: withParams,
    };
    // FIX: type
    const compiledAction: YamlStepOrAction = {
      name: a.name,
      provider: provider,
      condition: [compiledCondition],
    };
    if (foreach) compiledAction["foreach"] = foreach;
    return compiledAction;
  });
  return compiledActions;
}

export function getYamlStepFromStep(s: V2StepStep): YamlStepOrAction {
  const withParams = getWithParams(s);
  const providerType = s.type.replace("step-", "");
  const providerName =
    (s.properties.config as string)?.trim() || `default-${providerType}`;
  const provider = {
    type: s.type.replace("step-", ""),
    config: `{{ providers.${providerName} }}`,
    with: withParams,
  };
  const step: YamlStepOrAction = {
    name: s.name,
    provider: provider,
  };
  if (s.properties.vars) {
    step.vars = s.properties.vars;
  }
  return step;
}

export function getYamlActionFromAction(s: V2ActionStep): YamlStepOrAction {
  const withParams = getWithParams(s);
  const providerType = s.type.replace("action-", "");
  const ifParam = s.properties.if;
  const providerName =
    (s.properties.config as string)?.trim() || `default-${providerType}`;
  const provider = {
    type: s.type.replace("action-", ""),
    config: `{{ providers.${providerName} }}`,
    with: withParams,
  };
  const action: YamlStepOrAction = {
    name: s.name,
    provider: provider,
  };
  // add 'if' only if it's not empty
  if (ifParam) {
    action.if = ifParam as string;
  }
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
): YamlWorkflowDefinition {
  const alert = definition;
  const alertId = alert.properties.id as string;
  const name = (alert.properties.name as string) ?? "";
  const description = (alert.properties.description as string) ?? "";
  const disabled = alert.properties.disabled ?? false;
  const owners = (alert.properties.owners as string[]) ?? [];
  const services = (alert.properties.services as string[]) ?? [];
  const consts = (alert.properties.consts as Record<string, string>) ?? {};
  // Steps (move to func?)
  const steps = alert.sequence
    .filter((s): s is V2StepStep => s.type.startsWith("step-"))
    .map((s: V2StepStep) => getYamlStepFromStep(s));
  // Actions
  let actions = alert.sequence
    .filter((s): s is V2ActionStep => s.type.startsWith("action-"))
    .map((s: V2ActionStep) => getYamlActionFromAction(s));
  // Actions > Foreach
  alert.sequence
    .filter((step): step is V2StepForeach => step.type === "foreach")
    ?.forEach((forEach: V2StepForeach) => {
      const forEachValue = forEach?.properties?.value as string;
      // FIX: type
      const condition = forEach?.sequence?.find((c) =>
        c.type.startsWith("condition-")
      ) as unknown as V2StepConditionAssert | V2StepConditionThreshold;
      let foreachActions = [] as YamlStepOrAction[];
      if (condition) {
        foreachActions = getActionsFromCondition(condition, forEachValue);
      } else {
        const forEachSequence = forEach?.sequence || [];
        const stepOrAction = forEachSequence[0] as V2StepStep | V2ActionStep;
        if (!stepOrAction) {
          return;
        }
        const withParams = getWithParams(stepOrAction);
        const providerType = stepOrAction.type
          .replace("action-", "")
          .replace("step-", "");
        const ifParam = stepOrAction.properties.if;
        const providerName =
          (stepOrAction.properties.config as string)?.trim() ||
          `default-${providerType}`;
        const provider = {
          type: stepOrAction.type.replace("action-", "").replace("step-", ""),
          config: `{{ providers.${providerName} }}`,
          with: withParams,
        };
        const foreachAction: any = {
          name: stepOrAction.name || "",
          provider: provider,
          foreach: forEachValue,
        };
        if (ifParam) {
          foreachAction.if = ifParam as string;
        }
        if (stepOrAction.properties.vars) {
          foreachAction.vars = stepOrAction.properties.vars;
        }
        foreachActions = [foreachAction];
      }
      actions = [...actions, ...foreachActions];
    });
  // Actions > Condition
  alert.sequence
    .filter((step): step is V2StepConditionThreshold | V2StepConditionAssert =>
      step.type.startsWith("condition-")
    )
    ?.forEach((condition) => {
      const conditionActions = getActionsFromCondition(condition);
      actions = [...actions, ...conditionActions];
    });

  const triggers = [];
  if (alert.properties.manual === "true") triggers.push({ type: "manual" });
  if (
    alert.properties.alert &&
    Object.keys(alert.properties.alert).length > 0
  ) {
    const filters = Object.keys(alert.properties.alert).map((key) => {
      return {
        key: key,
        value: (alert.properties.alert as any)[key],
      };
    });
    triggers.push({
      type: "alert",
      filters: filters,
    });
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
  return {
    id: alertId,
    name: name,
    triggers: triggers,
    description: description,
    disabled: Boolean(disabled),
    owners: owners,
    services: services,
    consts: consts,
    steps: steps,
    actions: actions,
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
