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
  const providers: string[] = [];
  const secrets: string[] = [];
  const inputs: string[] = [];
  const alert: string[] = [];
  const incident: string[] = [];

  const variables = extractMustacheVariables(workflowYaml);
  variables.forEach((variable) => {
    const parts = variable.split(".");
    const firstPart = parts[0];
    const rest = parts.slice(1).join(".");
    switch (firstPart) {
      case "providers":
        providers.push(rest);
        break;
      case "secrets":
        secrets.push(rest);
        break;
      case "alert":
        alert.push(rest);
        break;
      case "incident":
        incident.push(rest);
        break;
      case "inputs":
        inputs.push(rest);
        break;
    }
  });

  return {
    providers: [...new Set(providers)],
    secrets: [...new Set(secrets)],
    inputs: [...new Set(inputs)],
    alert: [...new Set(alert)],
    incident: [...new Set(incident)],
  };
}
