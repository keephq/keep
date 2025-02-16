import { Provider } from "@/app/(keep)/providers/providers";
import { ToolboxConfiguration, V2Step } from "@/entities/workflows/model/types";

export const triggerTemplates = {
  manual: {
    type: "manual",
    componentType: "trigger",
    name: "Manual",
    id: "manual",
    properties: {
      manual: "true",
    },
  },
  alert: {
    type: "alert",
    componentType: "trigger",
    name: "Alert",
    id: "alert",
    properties: {
      alert: {
        source: "",
      },
    },
  },
  incident: {
    type: "incident",
    componentType: "trigger",
    name: "Incident",
    id: "incident",
    properties: {
      incident: {
        events: [],
      },
    },
  },
  interval: {
    type: "interval",
    componentType: "trigger",
    name: "Interval",
    id: "interval",
    properties: {
      interval: "",
    },
  },
};
export const triggerTypes = Object.keys(triggerTemplates);

export const TriggersGroup = {
  name: "Triggers",
  steps: [
    {
      type: "manual",
      componentType: "trigger",
      name: "Manual",
      id: "manual",
      properties: {
        manual: "true",
      },
    },
    {
      type: "interval",
      componentType: "trigger",
      name: "Interval",
      id: "interval",
      properties: {
        interval: "",
      },
    },
    {
      type: "alert",
      componentType: "trigger",
      name: "Alert",
      id: "alert",
      properties: {
        alert: {
          source: "",
        },
      },
    },
    {
      type: "incident",
      componentType: "trigger",
      name: "Incident",
      id: "incident",
      properties: {
        incident: {
          events: [],
        },
      },
    },
  ],
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

export const ConditionsGroup = {
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
};

export function getToolboxConfiguration(
  providers: Provider[]
): ToolboxConfiguration {
  /**
   * Generates the toolbox items
   */
  const [steps, actions] = providers.reduce(
    ([steps, actions], provider) => {
      const step = {
        componentType: "task",
        properties: {
          stepParams: provider.query_params ?? {},
          actionParams: provider.notify_params ?? {},
        },
      } as Partial<V2Step>;
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
    [[] as Partial<V2Step>[], [] as Partial<V2Step>[]]
  );
  return {
    groups: [
      TriggersGroup,
      {
        name: "Steps",
        steps: steps,
      },
      {
        name: "Actions",
        steps: actions,
      },
      MiscGroup,
      // TODO: get conditions from API,
      ConditionsGroup,
    ],
  };
}
