/**
 * Safely accesses nested object properties using dot notation
 * @param obj The object to traverse
 * @param path The dot-notation path to the desired property (e.g., 'annotations.summary')
 * @returns The value at the specified path, or undefined if the path doesn't exist
 */
export function getNestedValue(obj: any, path?: string | null): any {
  // Handle edge cases with nullish coalescing
  if (!obj || !path) {
    return undefined;
  }
  
  const keys = path.split('.');
  let value: any = obj;
  
  for (const key of keys) {
    // Use optional chaining pattern
    if (value && typeof value === "object" && key in value) {
      value = value[key as keyof typeof value];
    } else {
      return undefined;
    }
  }
  
  return value;
}
