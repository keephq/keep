import { FacetFilters } from "./alert-table-facet-types";
import { AlertDto, Severity } from "./models";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  UserCircleIcon,
  BellIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  CircleStackIcon,
  BellSlashIcon,
  FireIcon,
} from "@heroicons/react/24/outline";

export const getFilteredAlertsForFacet = (
  alerts: AlertDto[],
  facetFilters: FacetFilters,
  currentFacetKey: string,
  timeRange?: { start: Date; end: Date }
) => {
  return alerts.filter((alert) => {
    // First apply time range filter if exists
    if (timeRange) {
      const lastReceived = new Date(alert.lastReceived);
      if (lastReceived < timeRange.start || lastReceived > timeRange.end) {
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

export const getStatusIcon = (status: string) => {
  switch (status.toLowerCase()) {
    case "firing":
      return ExclamationCircleIcon;
    case "resolved":
      return CheckCircleIcon;
    case "acknowledged":
      return CircleStackIcon;
    default:
      return CircleStackIcon;
  }
};

export const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case "firing":
      return "red";
    case "resolved":
      return "green";
    case "acknowledged":
      return "blue";
    default:
      return "gray";
  }
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
