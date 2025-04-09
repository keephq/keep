export function buildNestedObject(
  acc: Record<string, any>,
  key: string,
  value: string
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
