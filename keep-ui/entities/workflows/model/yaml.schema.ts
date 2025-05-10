import { z } from "zod";
import {
  EnrichDisposableKeyValueSchema,
  EnrichKeyValueSchema,
  IncidentEventEnum,
  WithSchema,
} from "./schema";
import { Provider } from "@/shared/api/providers";
import { checkProviderNeedsInstallation } from "../lib/validation";

type ProviderMetadataForValidation = Pick<
  Provider,
  | "type"
  | "config"
  | "can_query"
  | "can_notify"
  | "query_params"
  | "notify_params"
>;

const mockProvider: ProviderMetadataForValidation = {
  type: "mock",
  config: {},
  can_query: true,
  can_notify: true,
  query_params: [],
  notify_params: [],
};

const githubStarsProvider: ProviderMetadataForValidation = {
  type: "github.stars",
  config: {
    access_token: {
      required: true,
      description: "GitHub Access Token",
      sensitive: true,
      default: null,
    },
  },
  can_query: true,
  can_notify: false,
  query_params: ["previous_stars_count", "last_stargazer", "repository"],
};

const auth0LogsProvider: ProviderMetadataForValidation = {
  type: "auth0.logs",
  config: {
    domain: {
      required: true,
      description: "Auth0 Domain",
      hint: "https://tenantname.us.auth0.com",
      validation: "https_url",
      default: null,
    },
    token: {
      required: true,
      sensitive: true,
      description: "Auth0 API Token",
      hint: "https://manage.auth0.com/dashboard/us/YOUR_ACCOUNT/apis/management/explorer",
      default: null,
    },
  },
  can_query: true,
  can_notify: false,
  query_params: ["log_type", "previous_users"],
};

export const WorkflowInputSchema = z.object({
  name: z.string(),
  type: z.string(),
  description: z.string().optional(),
  default: z.any().optional(),
  required: z.boolean().optional(),
  options: z.array(z.string()).optional(),
  visuallyRequired: z.boolean().optional(),
});

export type WorkflowInput = z.infer<typeof WorkflowInputSchema>;

const WorkflowStrategySchema = z.enum([
  "nonparallel_with_retry",
  "nonparallel",
  "parallel",
]);

export type WorkflowStrategy = z.infer<typeof WorkflowStrategySchema>;

const ManualTriggerSchema = z.object({
  type: z.literal("manual"),
});

const AlertTriggerSchema = z.object({
  type: z.literal("alert"),
  filters: z.array(z.object({ key: z.string(), value: z.string() })).optional(),
  cel: z.string().optional(),
  only_on_change: z.array(z.string()).optional(),
});

const IntervalTriggerSchema = z
  .object({
    type: z.literal("interval"),
    value: z.union([z.string(), z.number()]),
  })
  .strict();

const IncidentTriggerSchema = z
  .object({
    type: z.literal("incident"),
    events: z.array(IncidentEventEnum).min(1),
  })
  .strict();

const TriggerSchema = z.union([
  ManualTriggerSchema,
  AlertTriggerSchema,
  IntervalTriggerSchema,
  IncidentTriggerSchema,
]);

const YamlProviderSchema = z
  .object({
    type: z.string(),
    config: z.string().optional(),
    with: WithSchema,
  })
  .strict();

function getYamlProviderSchema(
  provider: ProviderMetadataForValidation,
  type: "step" | "action"
) {
  // Get all valid parameter keys from the provider
  const validKeys = [
    ...(type === "step"
      ? provider.query_params || []
      : provider.notify_params || []),
  ].filter((key) => key !== "kwargs");

  // TODO: use the correct type from the provider methods _query and _notify
  const valueSchema = z.union([
    z.string(),
    z.number(),
    z.boolean(),
    z.record(z.string(), z.any()),
    z.object({}),
    z.array(z.any()),
  ]);
  const withSchema = z.object({
    ...Object.fromEntries(
      // TODO: type each key with the correct type (backend should return types)
      validKeys.map((key) => [key, valueSchema.optional()])
    ),
    enrich_alert: EnrichDisposableKeyValueSchema.optional(),
    enrich_incident: EnrichKeyValueSchema.optional(),
  });

  if (provider.type === "mock") {
    return z.object({
      type: z.literal(provider.type),
      config: z.string().optional(),
      with: z.object({
        enrich_alert: EnrichDisposableKeyValueSchema.optional(),
        enrich_incident: EnrichKeyValueSchema.optional(),
      }),
    });
  }

  const configSchema = checkProviderNeedsInstallation(provider)
    ? z.string()
    : z.string().optional();

  return z
    .object({
      type: z.literal(provider.type),
      with: withSchema,
      config: configSchema,
    })
    .strict();
}

const YamlThresholdConditionSchema = z
  .object({
    id: z.string().optional(),
    name: z.string(),
    alias: z.string().optional(),
    type: z.literal("threshold"),
    value: z.string(),
    compare_to: z.union([z.string(), z.number()]),
    compare_type: z.enum(["gt", "lt"]).optional(),
    level: z.string().optional(),
  })
  .strict();

const YamlAssertConditionSchema = z
  .object({
    id: z.string().optional(),
    name: z.string(),
    alias: z.string().optional(),
    type: z.literal("assert"),
    assert: z.string(),
  })
  .strict();

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
    continue: z.boolean().optional(),
  })
  .strict();

const OnFailureSchema = z.object({
  retry: z.object({
    count: z.number(),
    interval: z.number(),
  }),
});

export const YamlWorkflowDefinitionSchema = z.object({
  workflow: z
    .object({
      id: z.string(),
      disabled: z.boolean().optional(),
      description: z.string().optional(),
      owners: z.array(z.string()).optional(),
      services: z.array(z.string()).optional(),
      steps: z.array(YamlStepOrActionSchema).optional(),
      actions: z.array(YamlStepOrActionSchema).optional(),
      triggers: z.array(TriggerSchema).min(1),
      name: z.string().optional(),
      consts: z.record(z.string(), z.string()).optional(),
      inputs: z.array(WorkflowInputSchema).optional(),
      strategy: WorkflowStrategySchema.optional(),
      "on-failure": OnFailureSchema.optional(),
      // [doe.john@example.com, doe.jane@example.com, NOC]
      permissions: z.array(z.string()).optional(),
    })
    .refine(
      (data) => {
        const hasSteps = data.steps && data.steps.length > 0;
        const hasActions = data.actions && data.actions.length > 0;
        return hasSteps || hasActions;
      },
      {
        message: "Workflow must have at least one step or action",
      }
    ),
});

export function getYamlWorkflowDefinitionSchema(
  providers: Provider[],
  { partial = false }: { partial?: boolean } = {}
) {
  let stepSchema: z.ZodSchema = YamlStepOrActionSchema;
  let actionSchema: z.ZodSchema = YamlStepOrActionSchema;
  // Only update schemas if there are providers
  const providersWithMock = [
    mockProvider,
    // TODO: move github and auth0 providers to the providers list from backend, once we have them at /providers endpoint
    githubStarsProvider,
    auth0LogsProvider,
    ...providers,
  ];
  const uniqueProviders = providersWithMock.reduce((acc, provider) => {
    if (!acc.find((p) => p.type === provider.type)) {
      acc.push(provider);
    }
    return acc;
  }, [] as ProviderMetadataForValidation[]);
  const providerStepSchemas = uniqueProviders
    .filter((provider) => provider.can_query)
    .map((provider) => getYamlProviderSchema(provider, "step"));
  stepSchema = YamlStepOrActionSchema.extend({
    // @ts-ignore TODO: fix type inference
    provider: z.discriminatedUnion("type", providerStepSchemas),
  });
  const providerActionSchemas = uniqueProviders
    .filter((provider) => provider.can_notify)
    .map((provider) => getYamlProviderSchema(provider, "action"));
  actionSchema = YamlStepOrActionSchema.extend({
    // @ts-ignore TODO: fix type inference
    provider: z.discriminatedUnion("type", providerActionSchemas),
  });
  const baseSchema = z.object({
    workflow: z.object({
      id: z.string(),
      disabled: z.boolean().optional(),
      name: z.string().min(1),
      description: z.string().min(1),
      owners: z.array(z.string()).optional(),
      // [doe.john@example.com, doe.jane@example.com, NOC]
      permissions: z.array(z.string()).optional(),
      services: z.array(z.string()).optional(),
      // optional will be replace on postProcess
      steps: z.array(stepSchema).optional(),
      actions: z.array(actionSchema).optional(),
      triggers: z.array(TriggerSchema).min(1),
      consts: z.record(z.string(), z.string()).optional(),
      inputs: z.array(WorkflowInputSchema).optional(),
      strategy: WorkflowStrategySchema.optional(),
      "on-failure": OnFailureSchema.optional(),
    }),
  });

  if (partial) {
    return baseSchema.extend({
      workflow: baseSchema.shape.workflow.extend({
        name: z.string().optional(),
        description: z.string().optional(),
        steps: z.array(stepSchema).optional(),
        actions: z.array(actionSchema).optional(),
        inputs: z.array(WorkflowInputSchema).optional(),
      }),
    });
  }

  return baseSchema;
}
