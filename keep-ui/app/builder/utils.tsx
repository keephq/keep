import { load, JSON_SCHEMA } from "js-yaml";
import { Provider } from "../providers/providers";
import {
  Definition,
  Step,
  StepDefinition,
  Uid,
} from "sequential-workflow-designer";
import { KeepStep } from "./types";
import { WrappedDefinition } from "sequential-workflow-designer-react";

export function getToolboxConfiguration(providers: {
  [providerType: string]: Provider;
}) {
  /**
   * Generates the toolbox items
   */
  const [steps, actions] = Object.values(providers).reduce(
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
    properties: {
      value: condition.value,
      compare_to: condition.compare_to,
    },
    branches: {
      true: [getActionOrStepObj(action, "action")],
      false: [],
    },
  };

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

export function buildAlert(definition: Definition): string {
  return "";
}
