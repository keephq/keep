/**
 * Extracts named groups names from a Python-style regex string.
 * @param regex - The python-regex string to extract named groups from, e.g., `(?P<group_name>...)`.
 */
export function extractNamedGroups(regex: string): string[] {
  const namedGroupPattern = /\(\?P<([a-zA-Z0-9_]+)>[^)]*\)/g;
  return Array.from(
    regex.matchAll(namedGroupPattern).map((execArray) => execArray[1])
  );
}
