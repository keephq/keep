import { ZodSchema } from "zod";
import zodToJsonSchema, { PostProcessCallback } from "zod-to-json-schema";

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

export function generateWorkflowYamlJsonSchema(zodSchema: ZodSchema) {
  return zodToJsonSchema(zodSchema, {
    name: "KeepWorkflowSchema",
    // Make workflow valid if it has either actions or steps
    postProcess: makeRequiredEitherStepsOrActions,
  });
}
