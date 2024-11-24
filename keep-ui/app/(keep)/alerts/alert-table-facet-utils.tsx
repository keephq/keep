import { FacetFilters } from "./alert-table-facet-types";
import { AlertDto } from "./models";
import { isQuickPresetRange } from "@/components/ui/DateRangePicker";

export const getFilteredAlertsForFacet = (
  alerts: AlertDto[],
  facetFilters: FacetFilters,
  currentFacetKey: string,
  timeRange?: { start: Date; end: Date; isFromCalendar: boolean }
) => {
  return alerts.filter((alert) => {
    // Only apply time range filter if both start and end dates exist
    if (timeRange?.start && timeRange?.end) {
      const lastReceived = new Date(alert.lastReceived);
      const rangeStart = new Date(timeRange.start);
      const rangeEnd = new Date(timeRange.end);

      if (!isQuickPresetRange(timeRange)) {
        rangeEnd.setHours(23, 59, 59, 999);
      }

      if (lastReceived < rangeStart || lastReceived > rangeEnd) {
        return false;
      }
    }

    // Then apply facet filters, excluding the current facet
    return Object.entries(facetFilters).every(([facetKey, includedValues]) => {
      // Skip filtering by current facet to avoid circular dependency
      if (facetKey === currentFacetKey || includedValues.length === 0) {
        return true;
      }

      let value;
      if (facetKey.includes(".")) {
        const [parentKey, childKey] = facetKey.split(".");
        const parentValue = alert[parentKey as keyof AlertDto];

        if (
          typeof parentValue === "object" &&
          parentValue !== null &&
          !Array.isArray(parentValue) &&
          !(parentValue instanceof Date)
        ) {
          value = (parentValue as Record<string, unknown>)[childKey];
        }
      } else {
        value = alert[facetKey as keyof AlertDto];
      }

      if (facetKey === "source") {
        const sources = value as string[];
        if (includedValues.includes("n/a")) {
          return !sources || sources.length === 0;
        }
        return (
          Array.isArray(sources) &&
          sources.some((source) => includedValues.includes(source))
        );
      }

      if (includedValues.includes("n/a")) {
        return value === null || value === undefined || value === "";
      }

      if (value === null || value === undefined || value === "") {
        return false;
      }

      return includedValues.includes(String(value));
    });
  });
};

export const getSeverityOrder = (severity: string): number => {
  switch (severity) {
    case "low":
      return 1;
    case "info":
      return 2;
    case "warning":
      return 3;
    case "error":
    case "high":
      return 4;
    case "critical":
      return 5;
    default:
      return 6;
  }
};
