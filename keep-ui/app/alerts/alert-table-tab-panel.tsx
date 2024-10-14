  import { AlertTable } from "./alert-table";
  import { useAlertTableCols } from "./alert-table-utils";
  import { AlertDto, AlertKnownKeys, Preset, getTabsFromPreset } from "./models";

  const getPresetAlerts = (alert: AlertDto, presetName: string): boolean => {
    if (presetName === "deleted") {
      return alert.deleted === true;
    }

    if (presetName === "groups") {
      return alert.group === true;
    }

    if (presetName === "feed") {
      return alert.deleted === false && alert.dismissed === false;
    }

    if (presetName === "dismissed") {
      return alert.dismissed === true;
    }

    if (presetName === "without-incident") {
      return alert.incident === null;
    }


    return true;
  };

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
    mutateAlerts
  }: Props) {
    const sortedPresetAlerts = alerts
      .filter((alert) => getPresetAlerts(alert, preset.name))
      .sort((a, b) => {
          // Shahar: we want noise alert first. If no noisy (most of the cases) we want the most recent first.
          const noisyA = (a.isNoisy && a.status == "firing") ? 1 : 0;
          const noisyB = (b.isNoisy && b.status == "firing") ? 1 : 0;

          // Primary sort based on noisy flag (true first)
          if (noisyA !== noisyB) {
              return noisyB - noisyA;
          }

          // Secondary sort based on time (most recent first)
          return b.lastReceived.getTime() - a.lastReceived.getTime();
    });

    const additionalColsToGenerate = [
      ...new Set(
        alerts
          .flatMap((alert) => Object.keys(alert))
          .filter((key) => AlertKnownKeys.includes(key) === false)
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
          presetStatic={preset.name === "feed" || preset.name === "groups" || preset.name === "dismissed" || preset.name === "without-incident"}
          presetId={preset.id}
          presetTabs={presetTabs}
          mutateAlerts={mutateAlerts}
      />
    );
  }
