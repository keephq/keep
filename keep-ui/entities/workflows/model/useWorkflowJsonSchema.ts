import { useProviders } from "@/utils/hooks/useProviders";
import { getYamlWorkflowDefinitionSchema } from "./yaml.schema";
import { useMemo } from "react";
import zodToJsonSchema, { PostProcessCallback } from "zod-to-json-schema";
import { YamlWorkflowDefinitionSchema } from "./yaml.schema";

const makeRequiredEitherStepsOrActions: PostProcessCallback = (
  // The original output produced by the package itself:
  jsonSchema,
  // The ZodSchema def used to produce the original schema:
  def,
  // The refs object containing the current path, passed options, etc.
  refs
) => {
  const path = refs.currentPath.join("/");
  if (
    jsonSchema &&
    path === "#/definitions/WorkflowSchema/properties/workflow"
  ) {
    // @ts-ignore
    jsonSchema.required = jsonSchema.required.filter(
      (r: string) => r !== "steps"
    );
    // @ts-ignore
    jsonSchema.anyOf = [
      {
        required: ["steps"],
        properties: {
          steps: { minItems: 1 },
        },
      },
      {
        required: ["actions"],
        properties: {
          actions: { minItems: 1 },
        },
      },
    ];
  }
  return jsonSchema;
};

export function useWorkflowJsonSchema() {
  const { data: { providers } = {} } = useProviders();
  return useMemo(() => {
    if (!providers) {
      return zodToJsonSchema(YamlWorkflowDefinitionSchema, {
        name: "WorkflowSchema",
        postProcess: makeRequiredEitherStepsOrActions,
      });
    }
    return zodToJsonSchema(getYamlWorkflowDefinitionSchema(providers), {
      name: "WorkflowSchema",
      // Make workflow valid if it has either actions or steps
      postProcess: makeRequiredEitherStepsOrActions,
    });
  }, [providers]);
}
