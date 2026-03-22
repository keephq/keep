import { useI18n } from "@/i18n/hooks/useI18n";
import { Badge } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import { DynamicImageProviderIcon } from "@/components/ui";

type AlertsFoundBadgeProps = {
  totalAlertsFound: number;
  alertsFound: AlertDto[];
  isLoading: boolean;
  role: "ruleCondition" | "correlationRuleConditions";
};

export const AlertsFoundBadge = ({
  totalAlertsFound,
  alertsFound,
  isLoading,
  role,
}: AlertsFoundBadgeProps) => {
  const { t } = useI18n();
  function renderFoundAlertsText() {
    const alertText = totalAlertsFound > 1
      ? t("rules.correlation.messages.alertsFoundPlural")
      : t("rules.correlation.messages.alertsFoundSingle");

    if (role === "ruleCondition") {
      return (
        <>
          {totalAlertsFound} {alertText} matching this condition
        </>
      );
    }

    return (
      <>
        {totalAlertsFound} {alertText} matching correlation rule conditions
      </>
    );
  }

  function getNotFoundText() {
    if (role === "ruleCondition") {
      return t("rules.correlation.messages.noAlertsFoundRuleCondition");
    }

    return t("rules.correlation.messages.noAlertsFoundCorrelationConditions");
  }

  if (totalAlertsFound === 0) {
    return (
      <Badge className="mt-3 w-full" color="gray">
        {isLoading ? t("rules.correlation.messages.gettingYourAlerts") : getNotFoundText()}
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
