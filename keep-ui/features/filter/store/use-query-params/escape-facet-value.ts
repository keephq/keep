export function escapeFacetValue(facetValue: string): string {
  if (facetValue.startsWith("'") && facetValue.endsWith("'")) {
    const unquoted = facetValue.slice(1, -1);
    const escaped = unquoted
      .replace(/\\/g, "\\\\") // escape backslash first
      .replace(/'/g, "\\'") // escape single quote
      .replace(/,/g, "\\,"); // escape comma
    return `'${escaped}'`;
  }

  return facetValue;
}
