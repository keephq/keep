import { useAlerts } from "@/entities/alerts/model/useAlerts";

export const usePresetAlertsCount = (
  presetCel: string,
  counterShowsFiringOnly: boolean
) => {
  const { useLastAlerts } = useAlerts();

  const celList = [];

  if (counterShowsFiringOnly) {
    celList.push("status == 'firing'");
  }

  celList.push(presetCel);

  const { totalCount, isLoading } = useLastAlerts({
    cel: celList
      .filter((cel) => !!cel)
      .map((cel) => `(${cel})`)
      .join(" && "),
    limit: 0,
    offset: 0,
  });

  return { totalCount, isLoading };
};
