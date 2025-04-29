import { parseWorkflowYamlStringToJSON } from "@/entities/workflows/lib/yaml-utils";
import { getYamlWorkflowDefinitionSchema } from "@/entities/workflows/model/yaml.schema";
import { getProviders } from "@/shared/api/providers";
import { createServerApiClient } from "@/shared/api/server";
import fs from "fs";
import path from "path";

function getWorkflowExamplesFiles() {
  const files = fs.readdirSync(
    path.join(__dirname, "../../examples/workflows")
  );
  return files.filter(
    (file) => file.endsWith(".yaml") || file.endsWith(".yml")
  );
}

async function validateWorkflowExamples() {
  const api = await createServerApiClient();

  const providersResponse = await getProviders(api);
  const providers = providersResponse.providers;
  const zodSchema = getYamlWorkflowDefinitionSchema(providers);
  const workflowFiles = getWorkflowExamplesFiles();

  workflowFiles.forEach((file) => {
    const workflowYaml = fs.readFileSync(
      path.join(__dirname, "../../examples/workflows", file),
      "utf8"
    );
    const workflowYamlObject = parseWorkflowYamlStringToJSON(workflowYaml);
    const name = workflowYamlObject.name;

    const result = zodSchema.safeParse(workflowYamlObject);
    if (!result.success) {
      console.error(`${name} is invalid`);
      console.error(result.error.format());
    } else {
      console.log(`${name} is valid`);
    }
  });
}

validateWorkflowExamples();
