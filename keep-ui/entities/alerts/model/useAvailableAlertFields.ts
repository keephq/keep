import { useSearchAlerts } from "@/utils/hooks/useSearchAlerts";
import { useMemo } from "react";
import { AlertDto } from ".";

const DAY = 3600 * 24;
const MAX_DEPTH = 10;

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
    const getNestedKeys = (obj: AlertDto, prefix = "", depth = 0): string[] => {
      if (depth > MAX_DEPTH) return [];
      return Object.entries(obj).reduce<string[]>((acc, [key, value]) => {
        const newKey = prefix ? `${prefix}.${key}` : key;
        if (value && typeof value === "object" && !Array.isArray(value)) {
          const nestedKeys = getNestedKeys(
            value as AlertDto,
            newKey,
            depth + 1
          );
          acc.push(...nestedKeys);
          return acc;
        }
        acc.push(newKey);
        return acc;
      }, []);
    };
    const uniqueFields = new Set<string>();
    alertsFound.forEach((alert: AlertDto) => {
      const alertKeys = getNestedKeys(alert);
      alertKeys.forEach((key) => uniqueFields.add(key));
    });
    return Array.from(uniqueFields);
  }, [alertsFound]);

  return { fields, isLoading };
};
