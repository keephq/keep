import {
  parseDocument,
  Document,
  Pair,
  Scalar,
  visit,
  isPair,
  isSeq,
  stringify,
  isMap,
} from "yaml";
import { Definition } from "../model/types";
import { getYamlWorkflowDefinition } from "./parser";

const YAML_STRINGIFY_OPTIONS = {
  indent: 2,
  lineWidth: -1,
};

export function getOrderedWorkflowYamlString(yamlString: string) {
  try {
    const content = yamlString.startsWith('"')
      ? JSON.parse(yamlString)
      : yamlString;
    const doc = parseDocument(content);

    orderDocument(doc);

    return doc.toString(YAML_STRINGIFY_OPTIONS);
  } catch (error) {
    console.error("Error ordering workflow yaml", error);
    return yamlString;
  }
}

/**
 * Orders the workflow sections according to the order of the fields in place (!)
 * @param doc
 * @returns
 */
function orderDocument(doc: Document) {
  const fieldsOrder = [
    "id",
    "name",
    "description",
    "disabled",
    "debug",
    "triggers",
    "consts",
    "owners",
    "services",
    "steps",
    "actions",
  ];
  const stepFieldsOrder = [
    "name",
    "foreach",
    "if",
    "condition",
    "provider",
    "with",
  ];
  const providerFieldsOrder = ["type", "config", "with"];

  try {
    const workflowSeq = doc.get("workflow");
    if (!workflowSeq || !isMap(workflowSeq)) {
      throw new Error("Workflow section not found");
    }
    workflowSeq.items.sort((a: Pair, b: Pair) => {
      const aKey = (a.key as Scalar).value as string;
      const bKey = (b.key as Scalar).value as string;
      const aIndex = fieldsOrder.indexOf(aKey);
      const bIndex = fieldsOrder.indexOf(bKey);

      // If both keys are known, sort by their order
      if (aIndex !== -1 && bIndex !== -1) {
        return aIndex - bIndex;
      }
      // If only a is known, it comes first
      if (aIndex !== -1) return -1;
      // If only b is known, it comes first
      if (bIndex !== -1) return 1;
      // If both are unknown, maintain original order
      return 0;
    });

    // Order steps
    const steps = workflowSeq.get("steps");
    if (steps && isSeq(steps)) {
      steps.items.forEach((step) => {
        if (isMap(step)) {
          step.items.sort((a: Pair, b: Pair) => {
            const aKey = (a.key as Scalar).value as string;
            const bKey = (b.key as Scalar).value as string;
            const aIndex = stepFieldsOrder.indexOf(aKey);
            const bIndex = stepFieldsOrder.indexOf(bKey);

            // If both keys are known, sort by their order
            if (aIndex !== -1 && bIndex !== -1) {
              return aIndex - bIndex;
            }
            // If only a is known, it comes first
            if (aIndex !== -1) return -1;
            // If only b is known, it comes first
            if (bIndex !== -1) return 1;
            // If both are unknown, maintain original order
            return 0;
          });

          // Order provider fields
          const provider = step.get("provider");
          if (provider && isMap(provider)) {
            provider.items.sort((a: Pair, b: Pair) => {
              const aKey = (a.key as Scalar).value as string;
              const bKey = (b.key as Scalar).value as string;
              const aIndex = providerFieldsOrder.indexOf(aKey);
              const bIndex = providerFieldsOrder.indexOf(bKey);

              // If both keys are known, sort by their order
              if (aIndex !== -1 && bIndex !== -1) {
                return aIndex - bIndex;
              }
              // If only a is known, it comes first
              if (aIndex !== -1) return -1;
              // If only b is known, it comes first
              if (bIndex !== -1) return 1;
              // If both are unknown, maintain original order
              return 0;
            });
          }
        }
      });
    }

    // Order actions
    const actions = workflowSeq.get("actions");
    if (actions && isSeq(actions)) {
      actions.items.forEach((action) => {
        if (isMap(action)) {
          action.items.sort((a: Pair, b: Pair) => {
            const aKey = (a.key as Scalar).value as string;
            const bKey = (b.key as Scalar).value as string;
            const aIndex = stepFieldsOrder.indexOf(aKey);
            const bIndex = stepFieldsOrder.indexOf(bKey);

            // If both keys are known, sort by their order
            if (aIndex !== -1 && bIndex !== -1) {
              return aIndex - bIndex;
            }
            // If only a is known, it comes first
            if (aIndex !== -1) return -1;
            // If only b is known, it comes first
            if (bIndex !== -1) return 1;
            // If both are unknown, maintain original order
            return 0;
          });

          // Order provider fields in actions
          const provider = action.get("provider");
          if (provider && isMap(provider)) {
            provider.items.sort((a: Pair, b: Pair) => {
              const aKey = (a.key as Scalar).value as string;
              const bKey = (b.key as Scalar).value as string;
              const aIndex = providerFieldsOrder.indexOf(aKey);
              const bIndex = providerFieldsOrder.indexOf(bKey);

              // If both keys are known, sort by their order
              if (aIndex !== -1 && bIndex !== -1) {
                return aIndex - bIndex;
              }
              // If only a is known, it comes first
              if (aIndex !== -1) return -1;
              // If only b is known, it comes first
              if (bIndex !== -1) return 1;
              // If both are unknown, maintain original order
              return 0;
            });
          }
        }
      });
    }
  } catch (error) {
    console.error("Error reordering workflow sections", error);
  }
}

export function getOrderedWorkflowYamlStringFromJSON(json: any) {
  const doc = new Document(json);
  orderDocument(doc);
  return doc.toString(YAML_STRINGIFY_OPTIONS);
}

export function parseWorkflowYamlStringToJSON(yamlString: string) {
  const content = yamlString.startsWith('"')
    ? JSON.parse(yamlString)
    : yamlString;
  return parseDocument(content).toJSON();
}

export function getCurrentPath(document: Document, absolutePosition: number) {
  let path: (string | number)[] = [];
  if (!document.contents) return [];

  visit(document, {
    Scalar(key, node, ancestors) {
      if (!node.range) return;
      if (
        absolutePosition >= node.range[0] &&
        absolutePosition <= node.range[2]
      ) {
        // Create a new array to store path components
        ancestors.forEach((ancestor, index) => {
          if (isPair(ancestor)) {
            path.push((ancestor.key as Scalar).value as string);
          } else if (isSeq(ancestor)) {
            // If ancestor is a Sequence, we need to find the index of the child item
            const childNode = ancestors[index + 1]; // Get the child node
            const seqIndex = ancestor.items.findIndex(
              (item) => item === childNode
            );
            if (seqIndex !== -1) {
              path.push(seqIndex);
            }
          }
        });
        return visit.BREAK;
      }
    },
  });

  return path;
}
export function getBodyFromStringOrDefinitionOrObject(
  definition: Definition | string | Record<string, unknown>
) {
  if (typeof definition === "string") {
    return definition;
  }
  if (typeof definition === "object" && "workflow" in definition) {
    return stringify(definition);
  }
  return stringify({
    workflow: getYamlWorkflowDefinition(definition as Definition),
  });
}
