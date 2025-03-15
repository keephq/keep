import { z } from "zod";
import { IncidentEventEnum } from "./types";
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

const EnrichAlertSchema = z.array(
  z.object({
    key: z.string(),
    value: z.string(),
  })
);

const EnrichIncidentSchema = z.array(
  z.object({
    key: z.string(),
    value: z.string(),
  })
);

const YamlProviderSchema = z.object({
  type: z.string(),
  config: z.string(),
  with: z
    .object({
      enrich_alert: EnrichAlertSchema.optional(),
      enrich_incident: EnrichIncidentSchema.optional(),
    })
    .catchall(
      z.union([
        z.string(),
        z.number(),
        z.boolean(),
        z.object({}),
        z.array(z.any()),
      ])
    ),
});

function getYamlProviderSchema(provider: Provider, type: "step" | "action") {
  // Get all valid parameter keys from the provider
  const validKeys = [
    ...(type === "step"
      ? provider.query_params || []
      : provider.notify_params || []),
    "enrich_alert",
    "enrich_incident",
  ];

  // @ts-ignore
  const validKeysSchema = z.enum(validKeys);

  return YamlProviderSchema.extend({
    type: z.literal(provider.type),
    with: z.record(
      validKeysSchema,
      z.union([
        z.string(),
        z.number(),
        z.boolean(),
        z.object({}),
        z.array(z.any()),
      ])
    ),
  });
}

export function getYamlWorkflowDefinitionSchema(providers: Provider[]) {
  const providerStepSchemas = providers
    .filter(
      (provider) => provider.query_params && provider.query_params.length > 0
    )
    .map((provider) => getYamlProviderSchema(provider, "step"));
  const stepSchema = YamlStepOrActionSchema.extend({
    // @ts-ignore TODO: fix type inference
    provider: z.discriminatedUnion("type", providerStepSchemas),
  });
  const providerActionSchemas = providers
    .filter(
      (provider) => provider.notify_params && provider.notify_params.length > 0
    )
    .map((provider) => getYamlProviderSchema(provider, "action"));
  const actionSchema = YamlStepOrActionSchema.extend({
    // @ts-ignore TODO: fix type inference
    provider: z.discriminatedUnion("type", providerActionSchemas),
  });
  return z.object({
    workflow: z.object({
      id: z.string(),
      disabled: z.boolean().optional(),
      description: z.string().optional(),
      owners: z.array(z.string()).optional(),
      services: z.array(z.string()).optional(),
      steps: z.array(stepSchema).min(1),
      actions: z.array(actionSchema).optional(),
      triggers: z.array(TriggerSchema).min(1),
      name: z.string().optional(),
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
