import { load, JSON_SCHEMA } from "js-yaml";
import { Provider } from "../../providers/providers";
import {
  BranchedStep,
  Definition,
  SequentialStep,
  Step,
  StepDefinition,
  Uid,
} from "sequential-workflow-designer";
import { KeepStep } from "./types";
import { Action, Alert } from "./alert";
import { stringify } from "yaml";

export function getToolboxConfiguration(providers: Provider[]) {
  /**
   * Generates the toolbox items
   */
  const [steps, actions] = providers.reduce(
    ([steps, actions], provider) => {
      const step = {
        componentType: "task",
        properties: {
          stepParams: provider.query_params!,
          actionParams: provider.notify_params!,
        },
      };
      if (provider.can_query)
        steps.push({
          ...step,
          type: `step-${provider.type}`,
          name: `${provider.type}-step`,
        });
      if (provider.can_notify)
        actions.push({
          ...step,
          type: `action-${provider.type}`,
          name: `${provider.type}-action`,
        });
      return [steps, actions];
    },
    [[] as StepDefinition[], [] as StepDefinition[]]
  );
  return {
    groups: [
      {
        name: "Steps",
        steps: steps,
      },
      {
        name: "Actions",
        steps: actions,
      },
      {
        name: "Misc",
        steps: [
          {
            type: "foreach",
            componentType: "container",
            name: "Foreach",
            properties: {},
            sequence: [],
          },
        ],
      },
      // TODO: get conditions from API
      {
        name: "Conditions",
        steps: [
          {
            type: "condition-threshold",
            componentType: "switch",
            name: "Threshold",
            properties: {
              value: "",
              compare_to: "",
            },
            branches: {
              true: [],
              false: [],
            },
          },
          {
            type: "condition-assert",
            componentType: "switch",
            name: "Assert",
            properties: {
              value: "",
              compare_to: "",
            },
            branches: {
              true: [],
              false: [],
            },
          },
        ],
      },
    ],
  };
}

export function getActionOrStepObj(
  actionOrStep: any,
  type: "action" | "step",
  providers?: Provider[]
): KeepStep {
  /**
   * Generate a step or action definition (both are kinda the same)
   */
  const providerType = actionOrStep.provider?.type;
  const provider = providers?.find((p) => p.type === providerType);
  return {
    id: Uid.next(),
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
    id: Uid.next(),
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
    id: Uid.next(),
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
  steps: Step[],
  conditions: Step[],
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
      isLocked: true,
      ...triggers,
    },
  };
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
  const steps = [] as any;
  const workflowSteps =
    workflow.steps?.map((s: any) => {
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
      if (currType === "alert" && curr.filters) {
        value = curr.filters.reduce((prev: any, curr: any) => {
          prev[curr.key] = curr.value;
          return prev;
        }, {});
      } else if (currType === "manual") {
        value = "true";
      }
      prev[currType] = value;
      return prev;
    }, {}) || {};

  return generateWorkflow(
    workflow.id,
    workflow.name,
    workflow.description,
    steps,
    conditions,
    triggers
  );
}

function getWithParams(s: Step): any {
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
  condition: BranchedStep,
  foreach?: string
): Action[] {
  const compiledCondition = {
    name: condition.name,
    type: condition.type.replace("condition-", ""),
    ...condition.properties,
  };
  const compiledActions = condition.branches.true.map((a) => {
    const withParams = getWithParams(a);
    const providerType = a.type.replace("action-", "");
    const providerName =
      (a.properties.config as string)?.trim() || `default-${providerType}`;
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

export function downloadFileFromString(data: string, filename: string) {
  /**
   * Generated with ChatGPT
   */
  var blob = new Blob([data], { type: "text/plain" });
  var url = URL.createObjectURL(blob);

  var link = document.createElement("a");
  link.href = url;
  link.download = filename;

  link.click();

  URL.revokeObjectURL(url);
}

export function buildAlert(definition: Definition): Alert {
  const alert = definition;
  const alertId = alert.properties.id as string;
  const name = (alert.properties.name as string) ?? "";
  const description = (alert.properties.description as string) ?? "";
  const owners = (alert.properties.owners as string[]) ?? [];
  const services = (alert.properties.services as string[]) ?? [];
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
      return {
        name: s.name,
        provider: provider,
      };
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
      // add 'if' only if it's not empty
      if (ifParam) {
        return {
          name: s.name,
          provider: provider,
          if: ifParam as string,
        };
      }
      else{
        return {
          name: s.name,
          provider: provider,
        };
      }
    });
  // Actions > Foreach
  alert.sequence
    .filter((step) => step.type === "foreach")
    ?.forEach((forEach) => {
      const forEachValue = forEach.properties.value as string;
      const condition = (forEach as SequentialStep).sequence.find((c) =>
        c.type.startsWith("condition-")
      ) as BranchedStep;
      let foreachActions = [] as Action[];
      if (condition) {
        foreachActions = getActionsFromCondition(condition, forEachValue);
      } else {
        const stepOrAction = (forEach as SequentialStep).sequence[0];
        const withParams = getWithParams(stepOrAction);
        const providerType = stepOrAction.type
          .replace("action-", "")
          .replace("step-", "");
        const ifParam = stepOrAction.properties.if;
        const providerName =
          (stepOrAction.properties.config as string)?.trim() ||
          `default-${providerType}`;
        const provider: any = {
          type: stepOrAction.type.replace("action-", "").replace("step-", ""),
          config: `{{ providers.${providerName} }}`,
          with: withParams,
        };
        foreachActions = [
          {
            name: stepOrAction.name,
            provider: provider,
            foreach: forEachValue,
            if: ifParam as string,
          },
        ];
      }
      actions = [...actions, ...foreachActions];
    });
  // Actions > Condition
  alert.sequence
    .filter((step) => step.type.startsWith("condition-"))
    ?.forEach((condition) => {
      const conditionActions = getActionsFromCondition(
        condition as BranchedStep
      );
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
  const compiledAlert = {
    id: alertId,
    name: name,
    triggers: triggers,
    description: description,
    owners: owners,
    services: services,
    steps: steps,
    actions: actions,
  };
  return compiledAlert;
}
