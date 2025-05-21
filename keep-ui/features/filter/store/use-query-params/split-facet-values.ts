/**
 * Splits a string of facet values into an array of individual values,
 * handling quoted strings and escaped characters.
 *
 * The input string can contain values separated by commas. If a value
 * is enclosed in single quotes, it will be treated as a single value
 * even if it contains commas. Backslashes can be used to escape characters.
 *
 * @param input - The input string containing facet values to be split.
 * @returns An array of strings, where each string is a trimmed facet value.
 *
 * @example
 * ```typescript
 * splitFacetValues("'value1','value,2','value\\'3'");
 * // Returns: ["'value1'", "'value,2'", "'value\\'3'"]
 * ```
 */
export function splitFacetValues(input: string) {
  const result = [];
  let current = "";
  let inQuotes = false;
  let escapeNext = false;

  for (let i = 0; i < input.length; i++) {
    const char = input[i];

    if (escapeNext) {
      current += char;
      escapeNext = false;
    } else if (char === "\\") {
      escapeNext = true;
      current += char;
    } else if (char === "'") {
      current += char;
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      result.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }

  if (current.length > 0) {
    result.push(current.trim());
  }

  return result;
}
