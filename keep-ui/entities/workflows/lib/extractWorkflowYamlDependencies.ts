import { extractMustacheVariables } from "./mustache";

export type WorkflowYamlDependencies = {
  providers: string[];
  secrets: string[];
  inputs: string[];
  alert: string[];
  incident: string[];
};

export function extractWorkflowYamlDependencies(
  workflowYaml: string
): WorkflowYamlDependencies {
  const providers: Set<string> = new Set();
  const secrets: Set<string> = new Set();
  const inputs: Set<string> = new Set();
  const alert: Set<string> = new Set();
  const incident: Set<string> = new Set();

  const variables = extractMustacheVariables(workflowYaml);
  variables.forEach((variable) => {
    const parts = variable.split(".");
    const firstPart = parts[0];
    const rest = parts.slice(1).join(".");
    switch (firstPart) {
      case "providers":
        providers.add(rest);
        break;
      case "secrets":
        secrets.add(rest);
        break;
      case "alert":
        alert.add(rest);
        break;
      case "incident":
        incident.add(rest);
        break;
      case "inputs":
        inputs.add(rest);
        break;
    }
  });

  return {
    providers: Array.from(providers),
    secrets: Array.from(secrets),
    inputs: Array.from(inputs),
    alert: Array.from(alert),
    incident: Array.from(incident),
  };
}
