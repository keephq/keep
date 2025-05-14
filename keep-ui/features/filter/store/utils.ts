export function valueToString(value: any): string {
  if (typeof value === "string") {
    /* Escape single-quote because single-quote is used for string literal mark*/
    const optionValue = value.replace(/'/g, "\\'");
    return `'${optionValue}'`;
  } else if (value == null) {
    return "null";
  }

  return `${value}`;
}

export function stringToValue(str: string): any {
  if (str === "null") {
    return null;
  }

  if (str.startsWith("'") && str.endsWith("'")) {
    return str.slice(1, -1).replace(/\\'/g, "'");
  }

  return JSON.parse(str);
}

export function toFacetState(values: string[]): Record<string, boolean> {
  return values.reduce(
    (acc, value) => {
      acc[value] = true;
      return acc;
    },
    {} as Record<string, boolean>
  );
}
