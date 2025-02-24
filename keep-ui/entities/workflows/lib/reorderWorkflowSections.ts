import { dump, load } from "js-yaml";

export function loadWorkflowIntoOrderedYaml(yamlString: string) {
  const content = yamlString.startsWith('"')
    ? JSON.parse(yamlString)
    : yamlString;

  const workflow = load(content) as any;
  const workflowData = workflow.workflow;

  const metadataFields = ["id", "name", "description", "disabled", "debug"];
  const sectionOrder = [
    "triggers",
    "consts",
    "owners",
    "services",
    "steps",
    "actions",
  ];

  const orderedWorkflow: any = {
    workflow: {},
  };

  metadataFields.forEach((field) => {
    if (workflowData[field] !== undefined) {
      orderedWorkflow.workflow[field] = workflowData[field];
    }
  });

  sectionOrder.forEach((section) => {
    if (workflowData[section] !== undefined) {
      orderedWorkflow.workflow[section] = workflowData[section];
      // TODO: order provider keys: config, type, with
    }
  });

  return dump(orderedWorkflow, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
    quotingType: '"',
  });
}
