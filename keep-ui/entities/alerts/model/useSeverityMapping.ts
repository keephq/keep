import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { AlertDto } from "./types";
import { getNestedValue } from "@/shared/lib/object-utils";

export interface SeverityMappingConfig {
  enabled: boolean;
  sourceField: string;
  mappings: Record<string, string>; // value → hex color
}

const defaultConfig: SeverityMappingConfig = {
  enabled: false,
  sourceField: "",
  mappings: {},
};

export function useSeverityMapping() {
  const [severityMapping, setSeverityMapping] =
    useLocalStorage<SeverityMappingConfig>("severity-mapping", defaultConfig);

  return { severityMapping, setSeverityMapping };
}

/**
 * Returns the custom color for an alert based on the mapping config,
 * or null if no mapping applies.
 */
export function getMappedColor(
  alert: AlertDto,
  config: SeverityMappingConfig
): string | null {
  if (!config.enabled || !config.sourceField) {
    return null;
  }

  const value = getNestedValue(alert, config.sourceField);
  if (value != null) {
    const stringValue = String(value);
    const color = config.mappings[stringValue];
    if (color && color.startsWith("#")) {
      return color;
    }
  }

  return null;
}
