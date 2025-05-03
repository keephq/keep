import { AlertsQuery, useAlerts } from "@/entities/alerts/model";
import { useDebouncedValue } from "@/utils/hooks/useDebouncedValue";
import { useEffect, useState } from "react";
import { formatQuery, RuleGroupType } from "react-querybuilder";

export function useMatchingAlerts(rules: RuleGroupType | undefined) {
  const { useLastAlerts } = useAlerts();
  const [debouncedRules] = useDebouncedValue(rules, 2000);
  const [alertsQuery, setAlertsQuery] = useState<AlertsQuery>();
  useEffect(() => {
    if (rules) {
      setAlertsQuery({
        cel: formatQuery(debouncedRules as RuleGroupType, "cel"),
        limit: 20,
        offset: 0,
      });
    }
  }, [debouncedRules]);

  return useLastAlerts(alertsQuery);
}
