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
      current += char; // preserve the backslash for now
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
