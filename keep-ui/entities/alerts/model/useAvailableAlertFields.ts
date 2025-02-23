import { useSearchAlerts } from "@/utils/hooks/useSearchAlerts";
import { useMemo } from "react";

const DAY = 3600 * 24;

export const useAvailableAlertFields = ({
  timeframe = DAY,
}: {
  timeframe?: number;
} = {}) => {
  const defaultQuery = {
    combinator: "or",
    rules: [
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
    ],
  };
  const { data: alertsFound = [], isLoading } = useSearchAlerts({
    query: defaultQuery,
    timeframe,
  });

  const fields = useMemo(() => {
    const getNestedKeys = (obj: any, prefix = ""): string[] => {
      return Object.entries(obj).reduce<string[]>((acc, [key, value]) => {
        const newKey = prefix ? `${prefix}.${key}` : key;
        if (value && typeof value === "object" && !Array.isArray(value)) {
          return [...acc, ...getNestedKeys(value, newKey)];
        }
        return [...acc, newKey];
      }, []);
    };
    return [
      ...alertsFound.reduce<Set<string>>((acc, alert) => {
        const alertKeys = getNestedKeys(alert);
        return new Set([...acc, ...alertKeys]);
      }, new Set<string>()),
    ];
  }, [alertsFound]);

  return { fields, isLoading };
};
