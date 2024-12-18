// TODO: move models to entities/alerts
import { useSearchAlerts } from "@/utils/hooks/useSearchAlerts";
import { Badge, Card, Text } from "@tremor/react";
import { parseCEL, RuleGroupType } from "react-querybuilder";

interface AlertsCountBadgeProps {
  presetCEL: string;
  isDebouncing: boolean;
  vertical?: boolean;
}

export const AlertsCountBadge: React.FC<AlertsCountBadgeProps> = ({
  presetCEL,
  isDebouncing,
  vertical = false,
}) => {
  console.log("AlertsCountBadge::presetCEL", presetCEL);
  // Create
  const defaultQuery: RuleGroupType = parseCEL(presetCEL) as RuleGroupType;

  // Parse CEL to RuleGroupType or use default empty rule group
  const parsedQuery = presetCEL
    ? (parseCEL(presetCEL) as RuleGroupType)
    : defaultQuery;

  // Add useSearchAlerts hook with proper typing
  const { data: alertsFound, isLoading: isSearching } = useSearchAlerts({
    query: parsedQuery,
    timeframe: 0,
  });

  console.log("AlertsCountBadge::swr", alertsFound);

  // Show loading state when searching or debouncing
  if (isSearching || isDebouncing) {
    return (
      <Card className="mt-4">
        <div className="flex justify-center">
          <div
            className={`flex ${
              vertical ? "flex-col" : "flex-row"
            } items-center gap-2`}
          >
            <Badge size="xl" color="orange">
              ...
            </Badge>
            <Text className="text-gray-500 text-sm">Searching...</Text>
          </div>
        </div>
      </Card>
    );
  }

  // Don't show anything if there's no data
  if (!alertsFound) {
    return null;
  }

  return (
    <Card className="mt-4">
      <div className="flex justify-center">
        <div
          className={`flex ${
            vertical ? "flex-col" : "flex-row"
          } items-center gap-2`}
        >
          <Badge size="xl" color="orange">
            {alertsFound.length}
          </Badge>
          <Text className="text-gray-500 text-sm">
            {alertsFound.length === 1 ? "Alert" : "Alerts"} found
          </Text>
        </div>
      </div>
      <Text className="text-center text-xs mt-2">
        These are the alerts that would match your preset
      </Text>
    </Card>
  );
};
