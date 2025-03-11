import { parseDocument, Document, YAMLMap } from "yaml";
import { z } from "zod";
import { ZodIssue } from "zod-validation-error";

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
  const reversedPath = path.toReversed();
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
function getNodeAtPath(doc: Document, path: (string | number)[]): any {
  if (!path || path.length === 0) return doc.contents;

  let current: any = doc.contents;

  for (const segment of path) {
    if (current instanceof YAMLMap) {
      // For objects
      const pair = current.items.find(
        (item) => item.key && item.key.value === segment
      );
      if (!pair) return undefined;
      current = pair.value;
    } else if (Array.isArray(current?.items)) {
      // For arrays
      if (typeof segment === "number" && segment < current.items.length) {
        current = current.items[segment];
      } else {
        return undefined;
      }
    } else {
      return undefined;
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
  const col = lines[lines.length - 1].length + 1;

  return { line, col };
}
