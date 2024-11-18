import { AlertTable } from "./alert-table";
import { useAlertTableCols } from "./alert-table-utils";
import { AlertDto, AlertKnownKeys, Preset, getTabsFromPreset } from "./models";

interface Props {
  alerts: AlertDto[];
  preset: Preset;
  isAsyncLoading: boolean;
  setTicketModalAlert: (alert: AlertDto | null) => void;
  setNoteModalAlert: (alert: AlertDto | null) => void;
  setRunWorkflowModalAlert: (alert: AlertDto | null) => void;
  setDismissModalAlert: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert: (alert: AlertDto | null) => void;
  mutateAlerts: () => void;
}

export default function AlertTableTabPanel({
  alerts,
  preset,
  isAsyncLoading,
  setTicketModalAlert,
  setNoteModalAlert,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  setChangeStatusAlert,
  mutateAlerts,
}: Props) {
  const sortedPresetAlerts = alerts.sort((a, b) => {
    // Shahar: we want noise alert first. If no noisy (most of the cases) we want the most recent first.
    const noisyA = a.isNoisy && a.status == "firing" ? 1 : 0;
    const noisyB = b.isNoisy && b.status == "firing" ? 1 : 0;

    // Primary sort based on noisy flag (true first)
    if (noisyA !== noisyB) {
      return noisyB - noisyA;
    }

    // Secondary sort based on time (most recent first)
    return b.lastReceived.getTime() - a.lastReceived.getTime();
  });

  const additionalColsToGenerate = [
    ...new Set(
      alerts.flatMap((alert) => {
        const keys = Object.keys(alert).filter(
          (key) => !AlertKnownKeys.includes(key)
        );
        return keys.flatMap((key) => {
          if (
            typeof alert[key as keyof AlertDto] === "object" &&
            alert[key as keyof AlertDto] !== null
          ) {
            return Object.keys(alert[key as keyof AlertDto] as object).map(
              (subKey) => `${key}.${subKey}`
            );
          }
          return key;
        });
      })
    ),
  ];

  const alertTableColumns = useAlertTableCols({
    additionalColsToGenerate: additionalColsToGenerate,
    isCheckboxDisplayed:
      preset.name !== "deleted" && preset.name !== "dismissed",
    isMenuDisplayed: true,
    setTicketModalAlert: setTicketModalAlert,
    setNoteModalAlert: setNoteModalAlert,
    setRunWorkflowModalAlert: setRunWorkflowModalAlert,
    setDismissModalAlert: setDismissModalAlert,
    setChangeStatusAlert: setChangeStatusAlert,
    presetName: preset.name,
    presetNoisy: preset.is_noisy,
  });

  const presetTabs = getTabsFromPreset(preset);

  return (
    <AlertTable
      alerts={sortedPresetAlerts}
      columns={alertTableColumns}
      setDismissedModalAlert={setDismissModalAlert}
      isAsyncLoading={isAsyncLoading}
      presetName={preset.name}
      presetPrivate={preset.is_private}
      presetNoisy={preset.is_noisy}
      presetStatic={preset.name === "feed"}
      presetId={preset.id}
      presetTabs={presetTabs}
      mutateAlerts={mutateAlerts}
    />
  );
}
