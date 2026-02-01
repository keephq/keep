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

function validateWorkflowExamples() {
  console.log("Loading providers list");
  // providers_list.json should be generated with "python3 scripts/save_providers_list.py" from the root of the repo
  const providers = JSON.parse(
    fs.readFileSync(path.join(__dirname, "../../providers_list.json"), "utf8")
  ) as any[];
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
      `❌ VALIDATION FAILED: ${invalidWorkflows.length}/${workflowFiles.length} workflows invalid`
    );
    console.log("\nINVALID FILES:");
    invalidWorkflows.forEach((file) => {
      console.log(`- ${file}`);
    });
    console.log("\nDetailed errors are shown above for each file.");
    console.log("\nHOW TO FIX:");
    console.log(
      "1. UI Editor: http://localhost:3000/workflows/ - Shows errors in real-time with highlighting"
    );
    console.log(
      "2. Schema: keep-ui/entities/workflows/model/yaml.schema.ts - Check if schema needs updates"
    );
    console.log(
      "3. Issues: https://github.com/keephq/keep/issues - Report if you believe it's a schema bug"
    );
    process.exit(1);
  } else {
    console.log(
      `✅ All ${workflowFiles.length} workflows are valid according to the schema. Nice!`
    );
  }
}

validateWorkflowExamples();
