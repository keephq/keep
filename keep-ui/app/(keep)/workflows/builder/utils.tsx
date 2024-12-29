import { load, JSON_SCHEMA } from "js-yaml";
import { Provider } from "../../providers/providers";
import { Action, Alert } from "./legacy-workflow.types";
import { v4 as uuidv4 } from "uuid";
import { z, ZodObject } from "zod";
import {
  Definition,
  V2Properties,
  V2Step,
} from "@/app/(keep)/workflows/builder/types";

export const contentTypeOptions = [
  {
    key: "application/json",
    value: "application/json",
    label: "application/json",
  },
  {
    key: "application/x-www-form-urlencoded",
    value: "application/x-www-form-urlencoded",
    label: "application/x-www-form-urlencoded",
  },
  {
    key: "multipart/form-data",
    value: "multipart/form-data",
    label: "multipart/form-data",
  },
  {
    key: "text/plain",
    value: "text/plain",
    label: "text/plain",
  },
];

export const methodOptions = [
  {
    value: "GET",
    key: "GET",
  },
  {
    key: "POST",
    value: "POST",
  },
  {
    value: "PUT",
    key: "PUT",
  },
  {
    value: "DELETE",
    key: "DELETE",
  },
  {
    key: "PATCH",
    value: "PATCH",
  },
];

export const requiredMap = {
  global: ["name", "description"],
  "action-http": ["url", "method"],
} as { [key: string]: string[] };

const triggers = [
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
];

const conditions = [
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
];

const miscs = [
  {
    type: "foreach",
    componentType: "container",
    name: "Foreach",
    properties: {},
    sequence: [],
  },
];

const toolsWithoutConfigState = [
  "action-http",
  ...triggers.map((trigger) => trigger.type),
  ...conditions.map((cond) => cond.type),
  ...miscs.map((misc) => misc.type),
];

const getStepsActionsFromProviders = (
  providers: Provider[],
  installed?: boolean
) => {
  return (
    providers.reduce(
      ([steps, actions], provider) => {
        const step = {
          componentType: "task",
          properties: {
            stepParams: provider.query_params!,
            actionParams: provider.notify_params!,
          },
          installed: installed,
        } as Partial<V2Step>;
        if (installed) {
          step.properties = {
            ...step.properties,
            config: provider?.details?.name || provider.id,
          };
        }
        if (provider.can_query)
          steps.push({
            ...step,
            type: `step-${provider.type}`,
            name: installed
              ? provider?.details?.name || provider.id
              : `${provider.type}-step`,
            id: provider.id, // to identify the provider.
          });
        if (provider.can_notify)
          actions.push({
            ...step,
            type: `action-${provider.type}`,
            name: installed
              ? provider?.details?.name || provider.id
              : `${provider.type}-action`,
          });
        return [steps, actions];
      },
      [[] as Partial<V2Step>[], [] as Partial<V2Step>[]]
    ) || [[], []]
  );
};

export function getToolboxConfiguration(
  providers: Provider[],
  installedProviders?: Provider[]
) {
  /**
   * Generates the toolbox items
   */
  const [steps, actions] = getStepsActionsFromProviders(providers);
  const [installedSteps, installedActions] = getStepsActionsFromProviders(
    installedProviders || [],
    true
  );
  const finalSteps = [...steps, ...installedSteps];
  const finalActionsSteps = [...actions, ...installedActions];
  return {
    groups: [
      {
        name: "Triggers",
        steps: triggers,
      },
      {
        name: "Steps",
        steps: finalSteps,
      },
      {
        name: "Actions",
        steps: finalActionsSteps,
      },
      {
        name: "Misc",
        steps: miscs,
      },
      // TODO: get conditions from API
      {
        name: "Conditions",
        steps: conditions,
      },
    ],
  };
}

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
        .replaceAll("providers.", "")
        .trim(),
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
  const parsedWorkflowFile = load(workflowString, {
    schema: JSON_SCHEMA,
  }) as any;
  return parsedWorkflowFile;
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
      (a?.properties?.config as string) || `default-${providerType}`;
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
  } as Alert;
}

export function wrapDefinitionV2({
  properties,
  sequence,
  isValid,
}: {
  properties: V2Properties;
  sequence: V2Step[];
  isValid?: boolean;
}) {
  return {
    value: {
      sequence: sequence,
      properties: properties,
    },
    isValid: !!isValid,
  };
}

const checkValidJson = (value?: string | object, allowEmpty?: boolean) => {
  try {
    if (value && Array.isArray(value)) {
      return false;
    }
    if (value && typeof value === "object") {
      return true;
    }
    if (allowEmpty && !value?.trim()) return true;
    const result = JSON.parse(value || "");
    if (value && Array.isArray(result)) {
      return false;
    }
    if (typeof result === "object") {
      return true;
    }
    return false;
  } catch {
    return false;
  }
};

const bodyBasedMethodSchema = z.object({
  method: z.enum(["POST", "PUT", "PATCH"]),
  body: z.union([z.string(), z.object({}).passthrough()]).refine(
    (value) => {
      const valid = checkValidJson(value, false);
      return valid;
    },
    { message: "Body must be valid JSON" }
  ),
  params: z
    .union([z.string(), z.object({}).passthrough()])
    .optional()
    .refine(
      (value) => {
        const valid = checkValidJson(value, true);
        return valid;
      },
      { message: "Params must be valid JSON" }
    ),
  headers: z
    .union([z.string(), z.object({}).passthrough()])
    .optional()
    .refine(
      (value) => {
        const valid = checkValidJson(value, true);
        return valid;
      },
      { message: "Headers must be valid JSON" }
    ),
});

// Schema for `GET` and `DELETE` methods
const paramsBasedMethodSchema = z.object({
  method: z.enum(["GET", "DELETE"]),
  params: z
    .union([z.string(), z.object({}).passthrough()])
    .optional()
    .refine(
      (value) => {
        const valid = checkValidJson(value, true);
        return valid;
      },
      { message: "Params must be valid JSON" }
    ),
  headers: z
    .union([z.string(), z.object({}).passthrough()])
    .optional()
    .refine(
      (value) => {
        const valid = checkValidJson(value, true);
        return valid;
      },
      { message: "Headers must be valid JSON" }
    ),
});

export const httpmethodSchema = z.discriminatedUnion("method", [
  bodyBasedMethodSchema,
  paramsBasedMethodSchema,
]);

const standardPropertiestSchema = z
  .object({
    name: z.string().min(1, { message: "Unique Identifier is mandatory" }),
    type: z.string().min(1, { message: "type is mandatory" }),
    properties: z
      .object({
        vars: z.object({}).passthrough().optional(),
        stepParams: z.array(z.string()).optional().nullable(),
        actionParams: z.array(z.string()).optional().nullable(),
        with: z
          .object({
            message: z.string().optional().nullable(),
            description: z.string().optional().nullable(),
          })
          .passthrough()
          .optional()
          .nullable(),
      })
      .passthrough(),
  })
  .passthrough();

const getUrlSchema = (optional?: boolean) => {
  if (optional)
    return z.object({
      url: z
        .string({ message: "Invalid url" })
        .url({ message: "Invalid url" })
        .optional(),
    });
  return z.object({
    url: z
      .string()
      .min(4, { message: "Invalid url" })
      .url({ message: "Invalid url" }),
  });
};

export type FormData = z.infer<ReturnType<typeof getSchemaByStepType>>;

const getConfigSchema = (type?: string) => {
  //we might need add some key to identify the provider stateless tools. for now doing it like this.

  if (type && toolsWithoutConfigState.includes(type)) {
    return z.object({ config: z.string().optional() });
  }
  return z.object({ config: z.string().min(2, "Provider is mandatory!") });
};

const customSchemaByType = (type?: string) => {
  let schema: ZodObject<any> = z.object({});
  switch (type) {
    case "action-http":
      schema = z
        .object({
          with: getUrlSchema().and(httpmethodSchema),
        })
        .passthrough();
      break;
    case "action-slack":
      schema = z.object({
        with: z.object({
          message: z.string().min(4, "Message should not be empty"),
        }),
      });
      break;
    case "condition-threshold":
      schema = z.object({
        value: z.string().min(1, "Value is required"),
        compare_to: z.string().min(1, "Compare to is required"),
      });
      break;
    case "condition-assert":
      schema = z.object({
        assert: z.string().min(4, "assert is required(eg:200==200)"),
      });
      break;
    case "foreach":
      schema = z.object({
        value: z.string().min(1, "value is required"),
      });
      break;
    default:
      break; //do nothing
  }

  return schema.passthrough();
};

export const getSchemaByStepType = (type?: string) => {
  // Validation based on type
  return z
    .object({
      properties: customSchemaByType(type).and(getConfigSchema(type)),
    })
    .passthrough()
    .and(standardPropertiestSchema);
};

export const standardWorkflowPropertiesSchema = z
  .object({
    name: z
      .string()
      .min(3, "Name is required and should be alteast 3 characters"),
    id: z.string().min(3, "id is required"),
    description: z
      .string()
      .min(4, "description is required and should be alteast 3 characters"),
    disbaled: z.enum(["true", "false"]).optional().nullable(),
    consts: z.object({}).passthrough().optional().nullable(),
  })
  .passthrough();

export const intervalSchema = z
  .object({
    interval: z
      .union([z.string(), z.number()])
      .optional()
      .nullable()
      .refine(
        (val) => {
          if (!val || !Number(val)) {
            return false;
          }
          return true;
        },
        { message: "Interval should be number" }
      ),
  })
  .passthrough();

export const alertSchema = z
  .object({
    alert: z
      .object({})
      .passthrough()
      .optional()
      .nullable()
      .refine(
        (data) => {
          // Check if the object is not empty
          return Object.values(data || {}).filter((val) => !!val).length > 0;
        },
        {
          message: "Workflow alert trigger cannot be empty.",
        }
      ),
  })
  .passthrough();

export const incidentSchema = z
  .object({
    incident: z
      .object({
        events: z
          .array(
            z.enum(["created", "updated", "deleted"], {
              message: "Workflow incident trigger cannot be empty.",
            })
          )
          .optional()
          .nullable(),
      })
      .optional()
      .nullable()
      .refine(
        (val) => {
          if (val && val?.events?.[0]) {
            return true;
          }
          return false;
        },
        { message: "Workflow incident trigger cannot be empty." }
      ),
  })
  .passthrough();

export const getWorkflowPropertiesSchema = (properties: V2Properties) => {
  let schema: ZodObject<any> = standardWorkflowPropertiesSchema;

  if ("interval" in properties) {
    schema = standardWorkflowPropertiesSchema.merge(intervalSchema);
  }
  if ("alert" in properties) {
    schema = standardWorkflowPropertiesSchema.merge(alertSchema);
  }
  if ("incident" in properties) {
    schema = standardWorkflowPropertiesSchema.merge(incidentSchema);
  }

  return schema;
};
