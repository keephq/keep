import { Badge } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import { DynamicImageProviderIcon } from "@/components/ui";

type AlertsFoundBadgeProps = {
  alertsFound: AlertDto[];
  isLoading: boolean;
  role: "ruleCondition" | "correlationRuleConditions";
};

export const AlertsFoundBadge = ({
  alertsFound,
  isLoading,
  role,
}: AlertsFoundBadgeProps) => {
  function renderFoundAlertsText() {
    if (role === "ruleCondition") {
      return (
        <>
          {alertsFound.length} alert{alertsFound.length > 1 ? "s" : ""} were
          found matching this condition
        </>
      );
    }

    return (
      <>
        {alertsFound.length} alert{alertsFound.length > 1 ? "s" : ""} were found
        matching correlation rule conditions
      </>
    );
  }

  if (alertsFound.length === 0) {
    return (
      <Badge className="mt-3 w-full" color="gray">
        {isLoading
          ? "Getting your alerts..."
          : "No alerts were found with this condition. Please try something else."}
      </Badge>
    );
  }

  const images = alertsFound.reduce<string[]>(
    (acc, { source }) => [...new Set([...acc, ...source])],
    []
  );

  return (
    <Badge className="mt-3 w-full" color="teal">
      <span className={"flex items-center justify-center flex-wrap"}>
        {images.map((source, index) => (
          <DynamicImageProviderIcon
            className={"inline-block -ml-2"}
            key={source}
            alt={source}
            height={24}
            width={24}
            title={source}
            src={`/icons/${source}-icon.png`}
          />
        ))}
        <span className="ml-4">{renderFoundAlertsText()}</span>
      </span>
    </Badge>
  );
};
