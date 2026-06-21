import { FacetDto } from "../models";

/**
 * Whether a facet should be deferred (collapsed, options loaded only on
 * expand). Only non-static lazy facets qualify — static facets such as
 * Severity/Status/Source must always render eagerly. The backend marks every
 * facet as `is_lazy: true` by default, so `is_static` is the real
 * discriminator here (#6577).
 */
export function isLazyFacet(facet: FacetDto): boolean {
  return !!facet.is_lazy && !facet.is_static;
}

export function valueToString(value: any): string {
  if (typeof value === "string") {
    /* Escape single-quote because single-quote is used for string literal mark*/
    const escaped = value
      .replace(/\\/g, "\\\\") // escape backslash
      .replace(/'/g, "\\'") // escape single quote
      .replace(/,/g, "\\,"); // escape comma
    return `'${escaped}'`;
  } else if (value === null || value === undefined) {
    return "null";
  } else if (typeof value === "boolean") {
    return `${value}`;
  } else if (typeof value === "number") {
    return `${value}`;
  }

  throw new Error("Unknown type of value is provided.");
}

export function stringToValue(str: string): any {
  if (str.startsWith("'") && str.endsWith("'")) {
    return str
      .slice(1, -1)
      .replace(/\\\\/g, "\\") // unescape backslash
      .replace(/\\'/g, "'") // unescape single quote
      .replace(/\\,/g, ","); // unescape comma
  }

  switch (str) {
    case "true":
      return true;
    case "false":
      return false;
    case "null":
      return null;
    default: {
      const number = Number.parseFloat(str);

      if (!Number.isNaN(number)) {
        return number;
      }
    }
  }

  throw new Error(`Unexpected string value provided: ${str}`);
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
