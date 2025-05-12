import {
  parseDocument,
  Document,
  Node,
  isMap,
  isSeq,
  isNode,
  isScalar,
} from "yaml";
import { z } from "zod";
import { ZodIssue } from "zod-validation-error";
import { YamlStepOrAction, YamlWorkflowDefinition } from "../model/yaml.types";
import { Provider } from "@/shared/api/providers";

/**
 * Extended error type that includes position information
 */
interface YamlValidationError {
  path: (string | number)[];
  message: string;
  line?: number;
  col?: number;
}

/**
 * Result of YAML validation
 */
export interface ValidationResult<T> {
  valid: boolean;
  data?: T;
  errors?: YamlValidationError[];
  document?: Document;
}

function getParentField(path: (string | number)[]) {
  const reversedPath = path.slice().reverse();
  if (typeof reversedPath[0] === "string") {
    return reversedPath[0];
  }
  if (typeof reversedPath[0] === "number") {
    return reversedPath[1] + " entries";
  }
  return null;
}

function getErrorMessage(err: ZodIssue) {
  let message = err.message;
  if (message.includes("Required") && err.path.length > 1) {
    message = `'${err.path[err.path.length - 1]}' field is required`;
    const parentField = getParentField(err.path.slice(0, -1));
    if (parentField) {
      message += ` in '${parentField}'`;
    }
  }
  return message;
}

/**
 * Validates a YAML string against a Zod schema with position information
 * @param yamlString YAML content as a string
 * @param schema Zod schema to validate against
 * @returns Validation result with position-aware errors if any
 */
export function validateYamlString<T>(
  yamlString: string,
  schema: z.ZodType<T>
): ValidationResult<T> {
  try {
    // Parse the YAML string into a Document
    const doc = parseDocument(yamlString);

    // Check if there are any YAML parsing errors
    if (doc.errors && doc.errors.length > 0) {
      return {
        valid: false,
        errors: doc.errors.map((err) => ({
          path: [],
          message: err.message,
          line:
            typeof err.linePos?.[0] === "number" ? err.linePos[0] : undefined,
          col:
            typeof err.linePos?.[1] === "number" ? err.linePos[1] : undefined,
        })),
      };
    }

    const yamlData = doc.toJS();

    // Validate using Zod
    const result = schema.safeParse(yamlData);

    if (!result.success) {
      // Transform Zod errors into position-aware errors
      const errors = result.error.errors.map((err) => {
        const error: YamlValidationError = {
          path: err.path,
          message: getErrorMessage(err),
        };

        // Try to find the node position in the document
        try {
          const node = getNodeAtPath(doc, err.path);
          if (node && node.range) {
            // Get position info from the node
            const positions = findLineAndColumn(yamlString, node.range[0]);
            if (positions) {
              error.line = positions.line;
              error.col = positions.col;
            }
          } else {
            // If we can't find the exact node, try to find the parent node
            const parentPath = err.path.slice(0, -1);
            const parentNode = getNodeAtPath(doc, parentPath);
            if (parentNode && parentNode.range) {
              const positions = findLineAndColumn(
                yamlString,
                parentNode.range[0]
              );
              if (positions) {
                error.line = positions.line;
                error.col = positions.col;
              }
            }
          }
        } catch (posError) {
          // If we can't get position, just return the error without position
          console.error("Error getting position info:", posError);
        }

        return error;
      });

      return {
        valid: false,
        errors,
        document: doc,
      };
    }

    return {
      valid: true,
      data: result.data,
      document: doc,
    };
  } catch (error) {
    return {
      valid: false,
      errors: [
        {
          path: [],
          message: `Error during validation: ${
            (error as Error)?.message ?? "Unknown error"
          }`,
        },
      ],
    };
  }
}

/**
 * Finds a node in the YAML document at the specified path
 * @param doc YAML Document
 * @param path Path to the node
 * @returns The node at the specified path or undefined
 */
function getNodeAtPath(doc: Document, path: (string | number)[]) {
  if (!path || path.length === 0) return doc.contents;

  let current: Node | null = doc.contents;

  for (const segment of path) {
    if (isMap(current)) {
      // For objects
      const pair = current.items.find(
        (item) =>
          item.key &&
          isNode(item.key) &&
          isScalar(item.key) &&
          item.key.value === segment
      );
      if (!pair) {
        return null;
      }
      current = pair.value as Node;
    } else if (isSeq(current)) {
      // For arrays
      if (typeof segment === "number" && segment < current.items.length) {
        current = current.items[segment] as Node;
      } else {
        return null;
      }
    } else {
      return null;
    }
  }

  return current;
}

/**
 * Finds line and column number for a given position in text
 * @param text The text content
 * @param position Character position
 * @returns Object with line and column numbers (1-based)
 */
function findLineAndColumn(
  text: string,
  position: number
): { line: number; col: number } | undefined {
  if (position < 0 || position >= text.length) return undefined;

  const lines = text.substring(0, position).split("\n");
  const line = lines.length;
  const tabWidth = 2;
  const col = lines[lines.length - 1].length + tabWidth;

  return { line, col };
}

export const validateMustacheVariableNameForYAML = (
  cleanedVariableName: string,
  currentStep: YamlStepOrAction,
  currentStepType: "step" | "action",
  definition: YamlWorkflowDefinition,
  secrets: Record<string, string>,
  providers: Provider[] | null,
  installedProviders: Provider[] | null
) => {
  if (!cleanedVariableName) {
    return ["Empty mustache variable.", "warning"];
  }
  const parts = cleanedVariableName.split(".");
  if (!parts.every((part) => part.length > 0)) {
    return [
      `Variable: ${cleanedVariableName} - path parts cannot be empty.`,
      "warning",
    ];
  }
  if (parts[0] === "providers") {
    const providerName = parts[1];
    if (!providerName) {
      return [
        `Variable: ${cleanedVariableName} - To access a provider, you need to specify the provider name.`,
        "warning",
      ];
    }
    if (!providers || !installedProviders) {
      // Skip validation if providers or installedProviders are not available
      return null;
    }
    const isDefault = providerName.startsWith("default-");
    if (isDefault) {
      const providerType = isDefault ? providerName.split("-")[1] : null;
      const provider = providers.find((p) => p.type === providerType);
      if (!provider) {
        return [
          `Variable: ${cleanedVariableName} - Provider "${providerName}" not found.`,
          "warning",
        ];
      }
    } else {
      const provider = installedProviders.find(
        (p) => p.details.name === providerName
      );
      if (!provider) {
        return [
          `Variable: ${cleanedVariableName} - Provider "${providerName}" is not installed.`,
          "warning",
        ];
      }
    }
    return null;
  }
  if (parts[0] === "alert") {
    // todo: validate alert properties
    return null;
  }
  if (parts[0] === "incident") {
    // todo: validate incident properties
    return null;
  }
  if (parts[0] === "secrets") {
    const secretName = parts[1];
    if (!secretName) {
      return [
        `Variable: ${cleanedVariableName} - To access a secret, you need to specify the secret name.`,
        "warning",
      ];
    }
    if (!secrets[secretName]) {
      return [
        `Variable: ${cleanedVariableName} - Secret "${secretName}" not found.`,
        "error",
      ];
    }
    return null;
  }
  if (parts[0] === "consts") {
    const constName = parts[1];
    if (!constName) {
      return [
        `Variable: ${cleanedVariableName} - To access a constant, you need to specify the constant name.`,
      ];
    }
    if (!definition.consts?.[constName]) {
      return [
        `Variable: ${cleanedVariableName} - Constant "${constName}" not found.`,
        "error",
      ];
    }
  }
  if (parts[0] === "steps") {
    const stepName = parts[1];
    if (!stepName) {
      return [
        `Variable: ${cleanedVariableName} - To access the results of a step, you need to specify the step name.`,
        "warning",
      ];
    }
    // todo: check if
    // - the step exists
    // - it's not the current step (can't access own results, only enrich_alert and enrich_incident can access their own results)
    // - it's above the current step
    // - if it's a step it cannot access actions since they run after steps
    const step = definition.steps.find((s) => s.name === stepName);
    const stepIndex = definition.steps.findIndex((s) => s.name === stepName);
    const currentStepIndex =
      currentStepType === "step"
        ? definition.steps.findIndex((s) => s.name === currentStep.name)
        : -1;
    if (!step) {
      return [
        `Variable: ${cleanedVariableName} - a "${stepName}" step doesn't exist.`,
        "error",
      ];
    }
    const isCurrentStep = step.name === currentStep.name;
    if (isCurrentStep) {
      return [
        `Variable: ${cleanedVariableName} - You can't access the results of the current step.`,
        "error",
      ];
    }
    if (currentStepIndex !== -1 && stepIndex > currentStepIndex) {
      return [
        `Variable: ${cleanedVariableName} - You can't access the results of a step that appears after the current step.`,
        "error",
      ];
    }

    if (!definition.steps?.some((step) => step.name === stepName)) {
      return [
        `Variable: ${cleanedVariableName} - a "${stepName}" step that doesn't exist.`,
        "error",
      ];
    }
    if (
      parts[2] === "results" ||
      parts[2].startsWith("results.") ||
      parts[2].startsWith("results[")
    ) {
      // todo: validate results properties
      return null;
    } else {
      return [
        `Variable: ${cleanedVariableName} - To access the results of a step, use "results" as suffix.`,
        "warning",
      ];
    }
  }
  return null;
};
