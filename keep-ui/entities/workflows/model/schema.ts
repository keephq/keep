import { z } from "zod";

const ManualTriggerValueSchema = z.literal("true");

export const V2StepManualTriggerSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
  type: z.literal("manual"),
  properties: z.object({
    manual: ManualTriggerValueSchema,
  }),
});

const IntervalTriggerValueSchema = z.union([z.string(), z.number()]);

export const V2StepIntervalTriggerSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
  type: z.literal("interval"),
  properties: z.object({
    interval: IntervalTriggerValueSchema,
  }),
});

const AlertTriggerValueSchema = z.record(z.string(), z.string());
export const V2StepAlertTriggerSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
  type: z.literal("alert"),
  properties: z.object({
    alert: AlertTriggerValueSchema,
    source: z.string().optional(),
  }),
  only_on_change: z.array(z.string()).optional(),
});

export const IncidentEventEnum = z.enum(["created", "updated", "deleted"]);

const IncidentTriggerValueSchema = z.object({
  events: z.array(IncidentEventEnum),
});
export const V2StepIncidentTriggerSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
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

export const EnrichDisposableKeyValueSchema = z.array(
  z.object({
    key: z.string(),
    value: z.string(),
    disposable: z.boolean().optional(),
  })
);

export const EnrichKeyValueSchema = z.array(
  z.object({
    key: z.string(),
    value: z.string(),
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
    value: z.string(),
    compare_to: z.string(),
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
});
