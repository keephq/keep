// TODO: move models to entities/alerts
import { useAlerts } from "@/utils/hooks/useAlerts";
import { Badge, Card, Text } from "@tremor/react";

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
  const { useLastAlerts } = useAlerts()
  const { totalCount, isLoading: isSearching } = useLastAlerts(
    presetCEL,
    20,
    0,
  );

  console.log("AlertsCountBadge::swr", totalCount);

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
  if (!Number.isInteger(totalCount)) {
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
            {totalCount}
          </Badge>
          <Text className="text-gray-500 text-sm">
            {totalCount === 1 ? "Alert" : "Alerts"} found
          </Text>
        </div>
      </div>
      <Text className="text-center text-xs mt-2">
        These are the alerts that would match your preset
      </Text>
    </Card>
  );
};
