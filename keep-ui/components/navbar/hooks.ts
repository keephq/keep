import { Preset } from "@/entities/presets/model/types";
import { useAlerts } from "@/utils/hooks/useAlerts";

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
    cel: celList.join(" && "),
    limit: 0,
    offset: 0,
  });

  return { totalCount, isLoading };
};
