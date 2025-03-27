import { z } from "zod";
import { IncidentEventEnum, WithSchema } from "./schema";
import { Provider } from "@/shared/api/providers";

const ManualTriggerSchema = z.object({
  type: z.literal("manual"),
});

const AlertTriggerSchema = z.object({
  type: z.literal("alert"),
  filters: z.array(z.object({ key: z.string(), value: z.string() })),
});

const IntervalTriggerSchema = z.object({
  type: z.literal("interval"),
  value: z.string(),
});

const IncidentTriggerSchema = z.object({
  type: z.literal("incident"),
  events: z.array(IncidentEventEnum).min(1),
});

const TriggerSchema = z.union([
  ManualTriggerSchema,
  AlertTriggerSchema,
  IntervalTriggerSchema,
  IncidentTriggerSchema,
]);

const YamlProviderSchema = z.object({
  type: z.string(),
  config: z.string(),
  with: WithSchema,
});

function getYamlProviderSchema(provider: Provider, type: "step" | "action") {
  // Get all valid parameter keys from the provider
  const validKeys = [
    ...(type === "step"
      ? provider.query_params || []
      : provider.notify_params || []),
    "enrich_alert",
    "enrich_incident",
  ].filter((key) => key !== "kwargs");

  if (validKeys.length === 0) {
    console.warn(
      `No valid keys found for provider ${provider.type} in ${type} mode`
    );
  }

  // @ts-ignore
  const validKeysSchema = z.enum(validKeys);

  // todo: find a way to merge record and enrich_alert/enrich_incident (objects)
  const withSchema = z.record(
    validKeysSchema,
    z.union([
      z.string(),
      z.number(),
      z.boolean(),
      z.record(z.string(), z.any()),
      z.object({}),
      z.array(z.any()),
    ])
  );

  return YamlProviderSchema.extend({
    type: z.literal(provider.type),
    with: withSchema,
  });
}

export function getYamlWorkflowDefinitionSchema(providers: Provider[]) {
  const providerStepSchemas = providers
    .filter((provider) => provider.can_query)
    .map((provider) => getYamlProviderSchema(provider, "step"));
  const stepSchema = YamlStepOrActionSchema.extend({
    // @ts-ignore TODO: fix type inference
    provider: z.discriminatedUnion("type", providerStepSchemas),
  });
  const providerActionSchemas = providers
    .filter((provider) => provider.can_notify)
    .map((provider) => getYamlProviderSchema(provider, "action"));
  const actionSchema = YamlStepOrActionSchema.extend({
    // @ts-ignore TODO: fix type inference
    provider: z.discriminatedUnion("type", providerActionSchemas),
  });
  return z.object({
    workflow: z.object({
      id: z.string(),
      disabled: z.boolean().optional(),
      name: z.string().min(1),
      description: z.string().min(1),
      owners: z.array(z.string()).optional(),
      services: z.array(z.string()).optional(),
      // optional will be replace on postProcess
      steps: z.array(stepSchema).optional(),
      actions: z.array(actionSchema).optional(),
      triggers: z.array(TriggerSchema).min(1),
      consts: z.record(z.string(), z.string()).optional(),
    }),
  });
}

const YamlThresholdConditionSchema = z.object({
  id: z.string().optional(),
  name: z.string(),
  alias: z.string().optional(),
  type: z.literal("threshold"),
  value: z.string(),
  compare_to: z.string(),
  level: z.string().optional(),
});

const YamlAssertConditionSchema = z.object({
  id: z.string().optional(),
  name: z.string(),
  alias: z.string().optional(),
  type: z.literal("assert"),
  assert: z.string(),
});

// TODO: generate schema runtime based on the providers
const YamlStepOrActionSchema = z
  .object({
    name: z.string(),
    provider: YamlProviderSchema,
    id: z.string().optional(),
    // todo: check `if` is valid
    if: z.string().optional(),
    vars: z.record(z.string(), z.string()).optional(),
    condition: z
      .array(z.union([YamlThresholdConditionSchema, YamlAssertConditionSchema]))
      .optional(),
    foreach: z.string().optional(),
  })
  .strict();

export const YamlWorkflowDefinitionSchema = z.object({
  workflow: z.object({
    id: z.string(),
    disabled: z.boolean().optional(),
    description: z.string().optional(),
    owners: z.array(z.string()).optional(),
    services: z.array(z.string()).optional(),
    steps: z.array(YamlStepOrActionSchema).min(1),
    actions: z.array(YamlStepOrActionSchema).optional(),
    triggers: z.array(TriggerSchema).min(1),
    name: z.string().optional(),
    consts: z.record(z.string(), z.string()).optional(),
  }),
});

export const LooseYamlWorkflowDefinitionSchema = z.object({
  workflow: z.object({
    id: z.string(),
    disabled: z.boolean().optional(),
    description: z.string().optional(),
    owners: z.array(z.string()).optional(),
    services: z.array(z.string()).optional(),
    steps: z.array(YamlStepOrActionSchema).optional(),
    actions: z.array(YamlStepOrActionSchema).optional(),
    triggers: z.array(TriggerSchema).optional(),
    name: z.string().optional(),
    consts: z.record(z.string(), z.string()).optional(),
  }),
});
