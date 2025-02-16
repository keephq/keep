import {
  Definition,
  DefinitionV2,
  V2Properties,
  V2Step,
} from "@/entities/workflows";
import { Provider } from "@/app/(keep)/providers/providers";
import { v4 as uuidv4 } from "uuid";
import { JSON_SCHEMA, load } from "js-yaml";
import {
  Action,
  LegacyWorkflow,
} from "@/entities/workflows/model/legacy-workflow.types";

export function getActionOrStepObj(
  actionOrStep: any,
  type: "action" | "step",
  providers?: Provider[]
): V2Step {
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
  actionOrStep: any,
  stepOrAction: "step" | "action",
  providers?: Provider[],
  sequence?: any
) {
  return {
    id: actionOrStep?.id || uuidv4(),
    type: "foreach",
    componentType: "container",
    name: "Foreach",
    properties: {
      value: actionOrStep.foreach,
    },
    sequence: [
      sequence ?? getActionOrStepObj(actionOrStep, stepOrAction, providers),
    ],
  };
}

export function generateCondition(
  condition: any,
  action: any,
  providers?: Provider[]
): any {
  const stepOrAction = action.type === "step" ? "step" : "action";
  const generatedCondition = {
    id: condition.id || uuidv4(),
    name: condition.name,
    type: `condition-${condition.type}`,
    componentType: "switch",
    alias: condition.alias,
    // TODO: this needs to be handled better
    properties: {
      value: condition.value,
      compare_to: condition.compare_to,
      assert: condition.assert,
    },
    branches: {
      true: [getActionOrStepObj(action, stepOrAction, providers)],
      false: [],
    },
  };

  // If this is a foreach, we need to add the foreach to the condition
  if (action.foreach) {
    return generateForeach(action, stepOrAction, providers, generatedCondition);
  }

  return generatedCondition;
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
  const steps = [] as V2Step[];
  const workflowSteps =
    workflow.steps?.map((s: V2Step) => {
      s.type = "step";
      return s;
    }) || [];
  const workflowActions = workflow.actions || [];
  const conditions = [] as any;
  [...workflowSteps, ...workflowActions].forEach((action: any) => {
    const stepOrAction = action.type === "step" ? "step" : "action";
    // This means this action always runs, there's no condition and no alias
    if (!action.condition && !action.if && !action.foreach) {
      steps.push(getActionOrStepObj(action, stepOrAction, providers));
    }
    // If this is an alias, we need to find the existing condition and add this action to it
    else if (action.if) {
      const cleanIf = action.if.replace("{{", "").replace("}}", "").trim();
      const existingCondition = conditions.find(
        (a: any) => a.alias === cleanIf
      );
      if (existingCondition) {
        existingCondition.branches.true.push(
          getActionOrStepObj(action, stepOrAction, providers)
        );
      } else {
        if (action.foreach) {
          steps.push(generateForeach(action, stepOrAction, providers));
        } else {
          steps.push(getActionOrStepObj(action, stepOrAction, providers));
        }
      }
    } else if (action.foreach) {
      steps.push(generateForeach(action, stepOrAction, providers));
    } else {
      action.condition.forEach((condition: any) => {
        conditions.push(generateCondition(condition, action, providers));
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

function getWithParams(s: V2Step): any {
  if (!s) {
    return;
  }
  s.properties = (s.properties || {}) as V2Properties;
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
  condition: V2Step,
  foreach?: string
): Action[] {
  const compiledCondition = {
    name: condition.name,
    type: condition.type.replace("condition-", ""),
    ...condition.properties,
  };
  const steps = condition?.branches?.true || ([] as V2Step[]);
  const compiledActions = steps.map((a: V2Step) => {
    const withParams = getWithParams(a);
    const providerType = a?.type?.replace("action-", "");
    const providerName =
      (a?.properties?.config as string)?.trim() || `default-${providerType}`;
    const provider = {
      type: a.type.replace("action-", ""),
      config: `{{ providers.${providerName} }}`,
      with: withParams,
    };
    const compiledAction = {
      name: a.name,
      provider: provider,
      condition: [compiledCondition],
    } as Action;
    if (foreach) compiledAction["foreach"] = foreach;
    return compiledAction;
  });
  return compiledActions;
}

export function getWorkflowFromDefinition(
  definition: Definition
): LegacyWorkflow {
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
    .filter((s) => s.type.startsWith("step-"))
    .map((s) => {
      const withParams = getWithParams(s);
      const providerType = s.type.replace("step-", "");
      const providerName =
        (s.properties.config as string)?.trim() || `default-${providerType}`;
      const provider = {
        type: s.type.replace("step-", ""),
        config: `{{ providers.${providerName} }}`,
        with: withParams,
      };
      const step: any = {
        name: s.name,
        provider: provider,
      };
      if (s.properties.vars) {
        step.vars = s.properties.vars;
      }
      return step;
    });
  // Actions
  let actions = alert.sequence
    .filter((s) => s.type.startsWith("action-"))
    .map((s) => {
      const withParams = getWithParams(s);
      const providerType = s.type.replace("action-", "");
      const ifParam = s.properties.if;
      const providerName =
        (s.properties.config as string)?.trim() || `default-${providerType}`;
      const provider: any = {
        type: s.type.replace("action-", ""),
        config: `{{ providers.${providerName} }}`,
        with: withParams,
      };
      const action: any = {
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
    });
  // Actions > Foreach
  alert.sequence
    .filter((step) => step.type === "foreach")
    ?.forEach((forEach) => {
      const forEachValue = forEach?.properties?.value as string;
      const condition = forEach?.sequence?.find((c) =>
        c.type.startsWith("condition-")
      ) as V2Step;
      let foreachActions = [] as Action[];
      if (condition) {
        foreachActions = getActionsFromCondition(condition, forEachValue);
      } else {
        const forEachSequence = forEach?.sequence || ([] as V2Step[]);
        const stepOrAction = forEachSequence[0] || ({} as V2Step[]);
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
    .filter((step) => step.type.startsWith("condition-"))
    ?.forEach((condition) => {
      const conditionActions = getActionsFromCondition(condition as V2Step);
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
  } as LegacyWorkflow;
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

export function getDefinitionFromNodesEdgesProperties(
  nodes: FlowNode[],
  edges: Edge[],
  _properties: V2Properties,
  validatorConfiguration: ValidatorConfigurationV2
): Definition {
  let { sequence, properties } =
    reConstructWorklowToDefinition({
      nodes,
      edges,
      properties: _properties,
    }) || {};
  sequence = (sequence || []) as V2Step[];
  properties = (properties || {}) as V2Properties;
  let isValid = true;
  for (let step of sequence) {
    isValid = validatorConfiguration?.step(step);
    if (!isValid) {
      break;
    }
  }
  if (isValid) {
    isValid = validatorConfiguration?.root({
      sequence,
      properties,
    });
  }
  return {
    sequence,
    properties,
    isValid,
  };
}
