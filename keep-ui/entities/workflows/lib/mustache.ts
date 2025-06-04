export const MUSTACHE_REGEX = /\{\{\s*(.*?)\s*\}\}/g;
export const ALLOWED_MUSTACHE_VARIABLE_REGEX = /^[a-zA-Z0-9._-\s]+$/;

/**
 * Extracts all mustache variables from a string.
 * @param yamlString - The string to extract mustache variables from.
 * @returns An array of mustache variables.
 *
 */
export function extractMustacheVariables(yamlString: string): string[] {
  // matchAll returns an iterator, so we convert it to an array with the spread operator
  // match[1] is match group 1, which is the variable name
  return (
    [...yamlString.matchAll(MUSTACHE_REGEX)]
      .map((match) => match[1])
      // TODO: more sophisticated validation
      .filter((variable) => variable.length > 0 && !variable.endsWith("."))
  );
}

/**
 * Extracts the trimmed value from mustache syntax by removing curly brackets.
 *
 * @param mustacheString - A string containing mustache syntax like "{{ variable }}"
 * @returns The trimmed inner value without curly brackets
 */
export function extractMustacheValue(mustacheString: string): string {
  // Use regex to match content between {{ and }} and trim whitespace
  const match = mustacheString.match(/\{\{\s*(.*?)\s*\}\}/);

  // Return the captured group if found, otherwise return empty string
  return match ? match[1] : "";
}
