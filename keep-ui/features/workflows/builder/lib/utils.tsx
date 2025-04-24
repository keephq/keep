import { Provider } from "@/shared/api/providers";
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

export const foreachTemplate: Omit<V2StepForeach, "id"> = {
  type: "foreach",
  componentType: "container",
  name: "Foreach",
  properties: {
    value: "",
  },
  sequence: [],
};

export const conditionThresholdTemplate: Omit<V2StepConditionThreshold, "id"> =
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
  };

export const conditionAssertTemplate: Omit<V2StepConditionAssert, "id"> = {
  type: "condition-assert",
  componentType: "switch",
  name: "Assert",
  properties: {
    assert: "",
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
          stepParams:
            provider.query_params?.filter((p) => p !== "kwargs") ?? [],
        },
      });
    }
    if (provider.can_notify) {
      actions.push({
        componentType: "task",
        type: `action-${provider.type}`,
        name: `${provider.type}-action`,
        properties: {
          actionParams:
            provider.notify_params?.filter((p) => p !== "kwargs") ?? [],
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

export const normalizeStepType = (type: string) => {
  return type
    ?.replace("step-", "")
    ?.replace("action-", "")
    ?.replace("__end", "")
    ?.replace("condition-", "")
    ?.replace("trigger_", "");
};

export function edgeCanHaveAddButton(source: string, target: string) {
  let showAddButton =
    !source?.includes("empty") &&
    !target?.includes("trigger_end") &&
    source !== "start";

  if (!showAddButton) {
    showAddButton =
      target?.includes("trigger_end") && source?.includes("trigger_start");
  }
  return showAddButton;
}

export function canAddTriggerBeforeEdge(source: string, target: string) {
  return source?.includes("trigger_start") && target?.includes("trigger_end");
}

export function canAddStepBeforeEdge(source: string, target: string) {
  return (
    !source?.includes("empty") &&
    !target?.includes("trigger_end") &&
    source !== "start"
  );
}

export function canAddConditionBeforeEdge(source: string, target: string) {
  return !target?.endsWith("empty_true") && !target?.endsWith("empty_false");
}

export function canAddForeachBeforeEdge(source: string, target: string) {
  return !target?.endsWith("foreach");
}
