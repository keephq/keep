import { getYamlWorkflowDefinitionSchema } from "../entities/workflows/model/yaml.schema";
import fs from "fs";
import path from "path";
import { generateWorkflowYamlJsonSchema } from "../entities/workflows/lib/generateWorkflowYamlJsonSchema";

function saveWorkflowYamlJsonSchema() {
  console.log("Loading providers list");
  // providers_list.json should be generated with "python3 scripts/save_providers_list.py" from the root of the repo
  const providers = JSON.parse(
    fs.readFileSync(path.join(__dirname, "../../providers_list.json"), "utf8")
  ) as any[];
  console.log(`Providers list loaded, ${providers.length} providers found`);
  const zodSchema = getYamlWorkflowDefinitionSchema(providers);
  console.log(`Zod schema loaded`);
  const jsonSchema = generateWorkflowYamlJsonSchema(zodSchema);
  fs.writeFileSync(
    path.join(__dirname, "../../workflow-yaml-json-schema.json"),
    JSON.stringify(jsonSchema, null, 2)
  );
  console.log("JSON schema generated");
}

saveWorkflowYamlJsonSchema();
