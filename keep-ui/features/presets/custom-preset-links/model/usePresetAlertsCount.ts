import { useAlerts } from "@/entities/alerts/model/useAlerts";

export const usePresetAlertsCount = (
  presetCel: string,
  counterShowsFiringOnly: boolean,
  limit = 0,
  offset = 0
) => {
  const { useLastAlerts } = useAlerts();

  const celList = [];

  if (counterShowsFiringOnly) {
    celList.push("status == 'firing'");
  }

  celList.push(presetCel);

  const { data, totalCount, isLoading } = useLastAlerts({
    cel: celList
      .filter((cel) => !!cel)
      .map((cel) => `(${cel})`)
      .join(" && "),
    limit: limit,
    offset: offset,
  });

  return { alerts: data, totalCount, isLoading };
};
