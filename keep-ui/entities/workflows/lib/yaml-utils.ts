import {
  parseDocument,
  Document,
  YAMLMap,
  Pair,
  Scalar,
  stringify,
} from "yaml";
import { Definition } from "../model/types";
import { getYamlWorkflowDefinition } from "./parser";

const YAML_STRINGIFY_OPTIONS = {
  indent: 2,
  lineWidth: -1,
};

export function getOrderedWorkflowYamlString(yamlString: string) {
  const content = yamlString.startsWith('"')
    ? JSON.parse(yamlString)
    : yamlString;
  const doc = parseDocument(content);

  orderDocument(doc);

  return doc.toString(YAML_STRINGIFY_OPTIONS);
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
  const stepFieldsOrder = ["name", "foreach", "if", "provider", "with"];
  const providerFieldsOrder = ["config", "type", "with"];
  // TODO: sort step props and provider props according to the order of the fields
  try {
    const workflowSeq = doc.get("workflow");
    if (!workflowSeq || !(workflowSeq instanceof YAMLMap)) {
      throw new Error("Workflow section not found");
    }
    workflowSeq.items.sort((a: Pair, b: Pair) => {
      // TODO: sort according to the order of the sections
      const aIndex = fieldsOrder.indexOf((a.key as Scalar).value as string);
      const bIndex = fieldsOrder.indexOf((b.key as Scalar).value as string);
      return aIndex > bIndex ? 1 : -1;
    });
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
