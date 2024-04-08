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
  setDismissModalAlert: (alert: AlertDto | null) => void;
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
    .sort((a, b) => b.lastReceived.getTime() - a.lastReceived.getTime());

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
  });

  return (
    <AlertTable
      alerts={sortedPresetAlerts}
      columns={alertTableColumns}
      isAsyncLoading={isAsyncLoading}
      presetName={preset.name}
    />
  );
}
