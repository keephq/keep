import { load, JSON_SCHEMA } from "js-yaml";
import { Provider } from "../providers/providers";
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
  type: "action" | "step"
): KeepStep {
  /**
   * Generate a step or action definition (both are kinda the same)
   */
  return {
    id: Uid.next(),
    name: actionOrStep.name,
    componentType: "task",
    type: `${type}-${actionOrStep.provider?.type}`,
    properties: {
      config: actionOrStep.provider?.config,
      with: actionOrStep.provider?.with,
    },
  };
}

export function generateCondition(condition: any, action: any): any {
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
      true: [getActionOrStepObj(action, "action")],
      false: [],
    },
  };

  // If this is a foreach, we need to add the foreach to the condition
  if (action.foreach) {
    return {
      id: Uid.next(),
      type: "foreach",
      componentType: "container",
      name: "Foreach",
      properties: {
        value: action.foreach,
      },
      sequence: [generatedCondition],
    };
  }

  return generatedCondition;
}

export function generateAlert(
  alertId: string,
  description: string,
  steps: Step[],
  conditions: Step[]
): Definition {
  /**
   * Generate the alert definition
   */
  const alert = {
    id: Uid.next(),
    name: "Workflow",
    componentType: "container",
    type: "alert",
    properties: {
      id: alertId,
      description: description,
      isLocked: true,
    },
    sequence: [...steps, ...conditions],
  };
  return { sequence: [alert], properties: {} };
}

export function parseAlert(alertToParse: string): Definition {
  /**
   * Parse the alert file and generate the definition
   */
  const parsedAlertFile = load(alertToParse, { schema: JSON_SCHEMA }) as any;
  const steps = parsedAlertFile.alert.steps.map((step: any) => {
    return getActionOrStepObj(step, "step");
  });
  const conditions = [] as any;
  parsedAlertFile.alert.actions.forEach((action: any) => {
    // This means this action always runs, there's no condition and no alias
    if (!action.condition && !action.if) {
      steps.push(getActionOrStepObj(action, "action"));
    }
    // If this is an alias, we need to find the existing condition and add this action to it
    else if (action.if) {
      const cleanIf = action.if.replace("{{", "").replace("}}", "").trim();
      const existingCondition = conditions.find(
        (a: any) => a.alias === cleanIf
      );
      existingCondition?.branches.true.push(
        getActionOrStepObj(action, "action")
      );
    } else {
      action.condition.forEach((condition: any) => {
        conditions.push(generateCondition(condition, action));
      });
    }
  });

  return generateAlert(
    parsedAlertFile.alert.id,
    parsedAlertFile.alert.description,
    steps,
    conditions
  );
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
    const compiledAction = {
      name: a.name,
      provider: {
        type: a.type.replace("action-", ""),
        config: a.properties.config,
        with: a.properties.with,
      },
      condition: compiledCondition,
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
  const alert = definition.sequence[0] as SequentialStep;
  const alertId = (alert.properties.id as string) ?? alert.name;
  const description = (alert.properties.description as string) ?? "";
  const owners = (alert.properties.owners as string[]) ?? [];
  const services = (alert.properties.services as string[]) ?? [];
  // Steps (move to func?)
  const steps = alert.sequence
    .filter((s) => s.type.startsWith("step-"))
    .map((s) => {
      const provider = {
        type: s.type.replace("step-", ""),
        config: s.properties.config as string,
        with:
          (s.properties.with as {
            [key: string]: string | number | boolean | object;
          }) ?? {},
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
      const provider = {
        type: s.type.replace("step-", ""),
        config: s.properties.config as string,
        with:
          (s.properties.with as {
            [key: string]: string | number | boolean | object;
          }) ?? {},
      };
      return {
        name: s.name,
        provider: provider,
      };
    });
  // Actions > Foreach
  alert.sequence
    .filter((step) => step.type === "foreach")
    ?.forEach((forEach) => {
      const forEachValue = forEach.properties.value as string;
      const condition = (forEach as SequentialStep).sequence.find((c) =>
        c.type.startsWith("condition-")
      ) as BranchedStep;
      const foreachActions = getActionsFromCondition(condition, forEachValue);
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
  const compiledAlert = {
    id: alertId,
    description: description,
    owners: owners,
    services: services,
    steps: steps,
    actions: actions,
  };
  console.log(compiledAlert);
  return compiledAlert;
}
