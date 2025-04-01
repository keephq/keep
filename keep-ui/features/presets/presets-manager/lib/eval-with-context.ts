// Culled from: https://stackoverflow.com/a/54372020/12627235
import {
  AlertDto,
  reverseSeverityMapping,
  severityMapping,
} from "@/entities/alerts/model";

const getAllMatches = (pattern: RegExp, string: string) =>
  // make sure string is a String, and make sure pattern has the /g flag
  String(string).match(new RegExp(pattern, "g"));
const sanitizeCELIntoJS = (celExpression: string): string => {
  // First, replace "contains" with "includes"
  let jsExpression = celExpression.replace(/contains/g, "includes");

  // Replace severity comparisons with mapped values
  jsExpression = jsExpression.replace(
    /severity\s*([<>]=?|==)\s*(\d+|"[^"]*")/g,
    (match, operator, value) => {
      let severityKey;

      if (/^\d+$/.test(value)) {
        // If the value is a number
        severityKey = severityMapping[Number(value)];
      } else {
        // If the value is a string
        severityKey = value.replace(/"/g, "").toLowerCase(); // Remove quotes from the string value and convert to lowercase
      }

      const severityValue = reverseSeverityMapping[severityKey];

      if (severityValue === undefined) {
        return match; // If no mapping found, return the original match
      }

      // For equality, directly replace with the severity level
      if (operator === "==") {
        return `severity == "${severityKey}"`;
      }

      // For greater than or less than, include multiple levels based on the mapping
      const levels = Object.entries(reverseSeverityMapping);
      let replacement = "";
      if (operator === ">") {
        const filteredLevels = levels
          .filter(([, level]) => level > severityValue)
          .map(([key]) => `severity == "${key}"`);
        replacement = filteredLevels.join(" || ");
      } else if (operator === "<") {
        const filteredLevels = levels
          .filter(([, level]) => level < severityValue)
          .map(([key]) => `severity == "${key}"`);
        replacement = filteredLevels.join(" || ");
      }

      return `(${replacement})`;
    }
  );

  // Convert 'in' syntax to '.includes()'
  jsExpression = jsExpression.replace(
    /(\w+)\s+in\s+\[([^\]]+)\]/g,
    (match, variable, list) => {
      // Split the list by commas, trim spaces, and wrap items in quotes if not already done
      const items = list
        .split(",")
        .map((item: string) => item.trim().replace(/^([^"]*)$/, '"$1"'));
      return `[${items.join(", ")}].includes(${variable})`;
    }
  );

  return jsExpression;
};
// this pattern is far from robust
const variablePattern = /[a-zA-Z$_][0-9a-zA-Z$_]*/;
const jsReservedWords = new Set([
  "break",
  "case",
  "catch",
  "class",
  "const",
  "continue",
  "debugger",
  "default",
  "delete",
  "do",
  "else",
  "export",
  "extends",
  "finally",
  "for",
  "function",
  "if",
  "import",
  "in",
  "instanceof",
  "new",
  "return",
  "super",
  "switch",
  "this",
  "throw",
  "try",
  "typeof",
  "var",
  "void",
  "while",
  "with",
  "yield",
]);
export const evalWithContext = (context: AlertDto, celExpression: string) => {
  try {
    if (celExpression.length === 0) {
      return new Function();
    }

    const jsExpression = sanitizeCELIntoJS(celExpression);
    let variables = (getAllMatches(variablePattern, jsExpression) ?? []).filter(
      (variable) => variable !== "true" && variable !== "false"
    );

    // filter reserved words from variables
    variables = variables.filter((variable) => !jsReservedWords.has(variable));
    const func = new Function(...variables, `return (${jsExpression})`);

    const args = variables.map((arg) =>
      Object.hasOwnProperty.call(context, arg)
        ? context[arg as keyof AlertDto]
        : undefined
    );

    return func(...args);
  } catch (error) {
    return;
  }
};
