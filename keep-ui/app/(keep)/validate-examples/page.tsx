"use server";

import path from "path";
import fs from "fs";
import { ValidateExamplesPageClient } from "./page.client";

const baseExamples = path.join(process.cwd(), "../examples/workflows");

function getWorkflowExamplesYamls() {
  const files = fs.readdirSync(baseExamples);
  return files
    .filter((file) => file.endsWith(".yaml") || file.endsWith(".yml"))
    .map((file) => {
      const workflowYaml = fs.readFileSync(
        path.join(baseExamples, file),
        "utf8"
      );
      return {
        name: file,
        content: workflowYaml,
      };
    });
}

export default async function ValidateExamplesPage() {
  const yamls = await getWorkflowExamplesYamls();
  return <ValidateExamplesPageClient files={yamls} />;
}
