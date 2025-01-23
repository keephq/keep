import { AlertTable } from "./alert-table";
import { AlertTableServerSide } from "./alert-table-server-side";
import { useAlertTableCols } from "./alert-table-utils";
import {
  AlertDto,
  AlertKnownKeys,
  getTabsFromPreset,
} from "@/entities/alerts/model";
import { Preset } from "@/entities/presets/model/types";

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
  onFilterCelChange: (filterCel: string) => void;
}

export default function AlertTableTabPanelServerSide({
  alerts,
  preset,
  isAsyncLoading,
  setTicketModalAlert,
  setNoteModalAlert,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  setChangeStatusAlert,
  mutateAlerts,
  onFilterCelChange,
}: Props) {
  const additionalColsToGenerate = [
    ...new Set(
      alerts?.flatMap((alert) => {
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
      }) || []
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
    <AlertTableServerSide
      alerts={alerts}
      columns={alertTableColumns}
      setDismissedModalAlert={setDismissModalAlert}
      isAsyncLoading={isAsyncLoading}
      presetName={preset.name}
      presetStatic={preset.name === "feed"}
      presetId={preset.id}
      presetTabs={presetTabs}
      mutateAlerts={mutateAlerts}
      setRunWorkflowModalAlert={setRunWorkflowModalAlert}
      setDismissModalAlert={setDismissModalAlert}
      setChangeStatusAlert={setChangeStatusAlert}
      onFilterCelChange={onFilterCelChange}
    />
  );
}
