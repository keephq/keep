import { z } from "zod";

const ManualTriggerValueSchema = z.literal("true");

export const WorkflowConstsSchema = z.record(
  z.string(),
  z.union([
    z.string(),
    z.number(),
    z.boolean(),
    z.record(z.string(), z.any()),
    z.object({}),
    z.array(z.any()),
  ])
);

const TriggerSchemaBase = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
});

export const V2StepManualTriggerSchema = TriggerSchemaBase.extend({
  type: z.literal("manual"),
  properties: z.object({
    manual: ManualTriggerValueSchema,
  }),
});

const IntervalTriggerValueSchema = z.union([z.string(), z.number()]);

export const V2StepIntervalTriggerSchema = TriggerSchemaBase.extend({
  type: z.literal("interval"),
  properties: z.object({
    interval: IntervalTriggerValueSchema,
  }),
});

const AlertTriggerValueSchema = z.record(z.string(), z.string());
export const V2StepAlertTriggerSchema = TriggerSchemaBase.extend({
  type: z.literal("alert"),
  properties: z
    .object({
      filters: z.record(z.string(), z.string()).optional(),
      cel: z.string().optional(),
      only_on_change: z.array(z.string()).optional(),
    })
    .optional(),
});

export const IncidentEventEnum = z.enum(["created", "updated", "deleted", "alert_association_changed"]);

const IncidentTriggerValueSchema = z.object({
  events: z.array(IncidentEventEnum),
});

export const V2StepIncidentTriggerSchema = TriggerSchemaBase.extend({
  type: z.literal("incident"),
  properties: z.object({
    incident: IncidentTriggerValueSchema,
  }),
});

export const V2StepTriggerSchema = z.union([
  V2StepManualTriggerSchema,
  V2StepIntervalTriggerSchema,
  V2StepAlertTriggerSchema,
  V2StepIncidentTriggerSchema,
]);

export const WorkflowInputTypeEnum = z.enum([
  "string",
  "number",
  "boolean",
  "choice",
]);

const WorkflowInputBaseSchema = z.object({
  name: z.string(),
  description: z.string().optional(),
  default: z.any().optional(),
  required: z.boolean().optional(),
  visuallyRequired: z.boolean().optional(), // For inputs without defaults that aren't explicitly required
});

const WorkflowInputStringSchema = WorkflowInputBaseSchema.extend({
  type: z.literal("string"),
  default: z.string().optional(),
});

const WorkflowInputNumberSchema = WorkflowInputBaseSchema.extend({
  type: z.literal("number"),
  default: z.number().optional(),
});

const WorkflowInputBooleanSchema = WorkflowInputBaseSchema.extend({
  type: z.literal("boolean"),
  default: z.boolean().optional(),
});

const WorkflowInputChoiceSchema = WorkflowInputBaseSchema.extend({
  type: z.literal("choice"),
  default: z.string().optional(),
  options: z.array(z.string()),
});

export const WorkflowInputSchema = z.discriminatedUnion("type", [
  WorkflowInputStringSchema,
  WorkflowInputNumberSchema,
  WorkflowInputBooleanSchema,
  WorkflowInputChoiceSchema,
]);

export const EnrichDisposableKeyValueSchema = z.array(
  z.object({
    key: z.string(),
    value: z.union([z.string(), z.number()]),
    disposable: z.boolean().optional(),
  })
);

export const EnrichKeyValueSchema = z.array(
  z.object({
    key: z.string(),
    value: z.union([z.string(), z.number()]),
  })
);

export const WithSchema = z
  .object({
    enrich_alert: EnrichDisposableKeyValueSchema.optional(),
    enrich_incident: EnrichKeyValueSchema.optional(),
  })
  .catchall(
    z.union([
      z.string(),
      z.number(),
      z.boolean(),
      z.record(z.string(), z.any()),
      z.object({}),
      z.array(z.any()),
    ])
  );

const RetrySchema = z.object({
  count: z.number().min(0).optional(),
  interval: z.number().min(0).optional(),
});

export const OnFailureSchema = z.object({
  retry: RetrySchema.optional(),
});

export const V2ActionSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("task"),
  type: z.string().startsWith("action"),
  properties: z.object({
    actionParams: z.array(z.string()),
    config: z.string().optional(),
    if: z.string().optional(),
    vars: z.record(z.string(), z.string()).optional(),
    with: WithSchema.optional(),
    "on-failure": OnFailureSchema.optional(),
  }),
});

export const V2StepStepSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("task"),
  type: z.string().startsWith("step"),
  properties: z.object({
    stepParams: z.array(z.string()),
    config: z.string().optional(),
    vars: z.record(z.string(), z.string()).optional(),
    if: z.string().optional(),
    with: WithSchema.optional(),
    "on-failure": OnFailureSchema.optional(),
  }),
});

export const V2ActionOrStepSchema = z.union([V2ActionSchema, V2StepStepSchema]);

export const V2StepConditionAssertSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("switch"),
  type: z.literal("condition-assert"),
  alias: z.string().optional(),
  properties: z.object({
    assert: z.string(),
  }),
  branches: z.object({
    true: z.array(V2ActionOrStepSchema),
    false: z.array(V2ActionOrStepSchema),
  }),
});

export const V2StepConditionThresholdSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("switch"),
  type: z.literal("condition-threshold"),
  alias: z.string().optional(),
  properties: z.object({
    value: z.union([z.string(), z.number()]),
    compare_to: z.union([z.string(), z.number()]),
  }),
  branches: z.object({
    true: z.array(V2ActionOrStepSchema),
    false: z.array(V2ActionOrStepSchema),
  }),
});

export const V2StepConditionSchema = z.union([
  V2StepConditionAssertSchema,
  V2StepConditionThresholdSchema,
]);

export const V2StepForeachSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("container"),
  type: z.literal("foreach"),
  properties: z.object({
    value: z.string(),
    if: z.string().optional(),
  }),
  // TODO: make a generic sequence type
  sequence: z.array(z.union([V2ActionOrStepSchema, V2StepConditionSchema])),
});

export const V2StepSchema = z.union([
  V2ActionSchema,
  V2StepStepSchema,
  V2StepConditionAssertSchema,
  V2StepConditionThresholdSchema,
  V2StepForeachSchema,
]);

export const V2StepTemplateSchema = z.union([
  V2ActionSchema.partial({ id: true }),
  V2StepStepSchema.partial({ id: true }),
  V2StepConditionAssertSchema.partial({ id: true }),
  V2StepConditionThresholdSchema.partial({ id: true }),
  V2StepForeachSchema.partial({ id: true }),
]);

export const NodeDataStepSchema = z.union([
  V2ActionSchema.partial({ id: true }),
  V2StepStepSchema.partial({ id: true }),
  V2StepConditionAssertSchema.partial({ id: true, branches: true }),
  V2StepConditionThresholdSchema.partial({ id: true, branches: true }),
  V2StepForeachSchema.partial({ id: true, sequence: true }),
]);

export const WorkflowPropertiesSchema = z.object({
  id: z.string(),
  name: z.string().min(1),
  description: z.string().min(1),
  disabled: z.boolean(),
  isLocked: z.boolean(),
  consts: z.record(z.string(), z.string()).optional(),
  alert: AlertTriggerValueSchema.optional(),
  interval: IntervalTriggerValueSchema.optional(),
  incident: IncidentTriggerValueSchema.optional(),
  manual: ManualTriggerValueSchema.optional(),
  services: z.array(z.string()).optional(),
  owners: z.array(z.string()).optional(),
  inputs: z.array(WorkflowInputSchema).optional(),
  "on-failure": V2ActionSchema.partial({
    id: true,
    name: true,
  })
    .extend(OnFailureSchema.shape)
    .optional(),
});
