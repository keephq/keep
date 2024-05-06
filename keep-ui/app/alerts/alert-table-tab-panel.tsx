  import { AlertTable } from "./alert-table";
  import { useAlertTableCols } from "./alert-table-utils";
  import { AlertDto, AlertKnownKeys, Preset } from "./models";

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
    setViewAlertModal: (alert: AlertDto) => void;
  }

  export default function AlertTableTabPanel({
    alerts,
    preset,
    isAsyncLoading,
    setTicketModalAlert,
    setNoteModalAlert,
    setRunWorkflowModalAlert,
    setDismissModalAlert,
    setViewAlertModal,
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
      setViewAlertModal: setViewAlertModal,
      presetName: preset.name,
      presetNoisy: preset.is_noisy,
    });

    return (
      <AlertTable
          alerts={sortedPresetAlerts}
          columns={alertTableColumns}
          setDismissedModalAlert={setDismissModalAlert}
          isAsyncLoading={isAsyncLoading}
          presetName={preset.name}
          presetPrivate={preset.is_private}
          presetNoisy={preset.is_noisy}
      />
    );
  }
