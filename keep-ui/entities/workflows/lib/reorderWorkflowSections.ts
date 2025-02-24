import { dump, load } from "js-yaml";

export function loadWorkflowIntoOrderedYaml(yamlString: string) {
  const content = yamlString.startsWith('"')
    ? JSON.parse(yamlString)
    : yamlString;

  const workflow = load(content) as any;
  const workflowData = workflow.workflow;

  const metadataFieldsOrder = [
    "id",
    "name",
    "description",
    "disabled",
    "debug",
  ];
  const sectionOrder = [
    "triggers",
    "consts",
    "owners",
    "services",
    "steps",
    "actions",
  ];
  const stepFieldsOrder = ["name", "foreach", "if", "provider", "with"];
  const providerFieldsOrder = ["config", "type", "with"];

  const orderedWorkflow: any = {
    workflow: {},
  };

  metadataFieldsOrder.forEach((field) => {
    if (workflowData[field] !== undefined) {
      orderedWorkflow.workflow[field] = workflowData[field];
    }
  });

  sectionOrder.forEach((section) => {
    if (workflowData[section] !== undefined) {
      if (section === "steps" || section === "actions") {
        orderedWorkflow.workflow[section] = workflowData[section].map(
          (item: any) => {
            const orderedItem: any = {};

            stepFieldsOrder.forEach((field) => {
              if (item[field] !== undefined) {
                if (field === "provider") {
                  const orderedProvider: any = {};
                  providerFieldsOrder.forEach((providerField) => {
                    if (item.provider[providerField] !== undefined) {
                      orderedProvider[providerField] =
                        item.provider[providerField];
                    }
                  });
                  orderedItem.provider = orderedProvider;
                } else {
                  orderedItem[field] = item[field];
                }
              }
            });

            Object.keys(item).forEach((field) => {
              if (!stepFieldsOrder.includes(field)) {
                orderedItem[field] = item[field];
              }
            });

            return orderedItem;
          }
        );
      } else {
        orderedWorkflow.workflow[section] = workflowData[section];
      }
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
