import { Provider } from "@/app/(keep)/providers/providers";
import {
  ToolboxConfiguration,
  V2StepConditionThreshold,
  V2StepConditionAssert,
  V2StepForeach,
  V2StepTrigger,
  V2StepStep,
  V2ActionStep,
} from "@/entities/workflows/model/types";

const manualTriggerTemplate: V2StepTrigger = {
  type: "manual",
  componentType: "trigger",
  name: "Manual",
  id: "manual",
  properties: {
    manual: "true",
  },
};

const alertTriggerTemplate: V2StepTrigger = {
  type: "alert",
  componentType: "trigger",
  name: "Alert",
  id: "alert",
  properties: {
    alert: {
      source: "",
    },
  },
};

const incidentTriggerTemplate: V2StepTrigger = {
  type: "incident",
  componentType: "trigger",
  name: "Incident",
  id: "incident",
  properties: {
    incident: {
      events: [],
    },
  },
};

const intervalTriggerTemplate: V2StepTrigger = {
  type: "interval",
  componentType: "trigger",
  name: "Interval",
  id: "interval",
  properties: {
    interval: "",
  },
};

export const getTriggerTemplate = (triggerType: string) => {
  if (triggerType === "manual") {
    return manualTriggerTemplate;
  }
  if (triggerType === "alert") {
    return alertTriggerTemplate;
  }
  if (triggerType === "incident") {
    return incidentTriggerTemplate;
  }
  if (triggerType === "interval") {
    return intervalTriggerTemplate;
  }
  throw new Error(`Trigger type ${triggerType} is not supported`);
};

export const triggerTypes = ["manual", "alert", "incident", "interval"];

const foreachTemplate: Omit<V2StepForeach, "id"> = {
  type: "foreach",
  componentType: "container",
  name: "Foreach",
  properties: {
    value: "",
  },
  sequence: [],
};

export const MiscGroup = {
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
};

const conditionThresholdTemplate: Omit<V2StepConditionThreshold, "id"> = {
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
};

const conditionAssertTemplate: Omit<V2StepConditionAssert, "id"> = {
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
};

export function getToolboxConfiguration(
  providers: Provider[]
): ToolboxConfiguration {
  /**
   * Generates the toolbox items
   */
  const steps: Omit<V2StepStep, "id">[] = [];
  const actions: Omit<V2ActionStep, "id">[] = [];

  for (const provider of providers) {
    if (provider.can_query) {
      steps.push({
        componentType: "task",
        type: `step-${provider.type}`,
        name: `${provider.type}-step`,
        properties: {
          stepParams: provider.query_params ?? [],
        },
      });
    }
    if (provider.can_notify) {
      actions.push({
        componentType: "task",
        type: `action-${provider.type}`,
        name: `${provider.type}-action`,
        properties: {
          actionParams: provider.notify_params ?? [],
        },
      });
    }
  }

  return {
    groups: [
      {
        name: "Triggers",
        steps: [
          manualTriggerTemplate,
          alertTriggerTemplate,
          incidentTriggerTemplate,
          intervalTriggerTemplate,
        ],
      },
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
        steps: [foreachTemplate],
      },
      // TODO: get conditions from API,
      {
        name: "Conditions",
        steps: [conditionThresholdTemplate, conditionAssertTemplate],
      },
    ],
  };
}
