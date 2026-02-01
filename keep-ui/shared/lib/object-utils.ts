/**
 * USAGE NOTE:
 * These utility functions for working with nested objects have some important behavioral differences:
 * 
 * - getNestedValue: Can access array elements using numeric indices (e.g., 'users.0.name')
 * - buildNestedObject: Creates objects with numeric string keys, NOT arrays (e.g., 'users.0.name' produces { users: { "0": { name: value } } })
 * - Neither function can handle property names that contain dots
 * 
 * Be aware of these differences when using these functions together.
 */

/**
 * Safely accesses nested object properties using dot notation
 * @param obj The object to traverse
 * @param path The dot-notation path to the desired property (e.g., 'annotations.summary')
 * @returns The value at the specified path, or undefined if the path doesn't exist
 * 
 * @example
 * // Access array element
 * getNestedValue({ users: ["Alice", "Bob"] }, "users.1") // Returns "Bob"
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

/**
 * Builds a nested object structure based on a dot-notation path and sets a value
 * at the specified location.
 * 
 * @param acc The accumulator object to build upon (can be empty or contain existing properties)
 * @param key The dot-notation path where the value should be set (e.g., 'user.address.city')
 * @param value The value to set at the specified path
 * @returns The modified accumulator object with the nested structure and value
 * 
 * @example
 * // Creates { user: { name: "John" } }
 * buildNestedObject({}, "user.name", "John")
 * 
 * @example
 * // Adds to existing object without overwriting other properties
 * // Returns { user: { name: "John", age: 30, address: { city: "New York" } } }
 * buildNestedObject({ user: { name: "John", age: 30 } }, "user.address.city", "New York")
 * 
 * @example
 * // Note: using numeric indices creates objects with string keys, NOT arrays
 * // Returns { users: { "0": { name: "John" } } }
 * buildNestedObject({}, "users.0.name", "John")
 */
export function buildNestedObject(
  acc: Record<string, any>,
  key: string,
  value: string | number | boolean | string[] | number[] | boolean[]
) {
  const keys = key.split(".");
  let current = acc;

  for (let i = 0; i < keys.length - 1; i++) {
    const part = keys[i];
    current[part] = current[part] || {};
    current = current[part];
  }

  current[keys[keys.length - 1]] = value;
  return acc;
}
