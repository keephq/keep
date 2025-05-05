import { fromError, fromZodError } from "zod-validation-error";
import { parseWorkflowYamlToJSON } from "../entities/workflows/lib/yaml-utils";
import { getYamlWorkflowDefinitionSchema } from "../entities/workflows/model/yaml.schema";
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
  console.log("Loading providers list");
  // providers_list.json should be generated with "python3 scripts/save_providers_list.py" from the root of the repo
  const providers = JSON.parse(
    fs.readFileSync(path.join(__dirname, "../../providers_list.json"), "utf8")
  );
  console.log(`Providers list loaded, ${providers.length} providers found`);
  const zodSchema = getYamlWorkflowDefinitionSchema(providers);
  console.log(`Zod schema loaded`);
  const workflowFiles = getWorkflowExamplesFiles();

  const invalidWorkflows: string[] = [];
  let validWorkflowsCount = 0;

  console.log(`Found ${workflowFiles.length} workflow files to validate`);

  workflowFiles.forEach((file) => {
    const workflowYaml = fs.readFileSync(
      path.join(__dirname, "../../examples/workflows", file),
      "utf8"
    );
    const result = parseWorkflowYamlToJSON(workflowYaml, zodSchema);

    if (!result.success) {
      console.log(`\n========== ${file} is invalid ==========`);
      console.log(fromZodError(result.error).toString());
      invalidWorkflows.push(file);
    } else {
      validWorkflowsCount++;
    }
  });

  console.log(`\n========================================= `);
  if (invalidWorkflows.length > 0) {
    console.log(
      `❌ ${invalidWorkflows.length} workflows are invalid out of ${workflowFiles.length} examples`
    );
    console.log("Please fix the following workflow files:");
    invalidWorkflows.forEach((file) => {
      console.log(`- ${file}`);
    });
    process.exit(1);
  } else {
    console.log(
      `✅ All ${workflowFiles.length} workflows are valid according to the schema. Nice!`
    );
  }
}

validateWorkflowExamples();
