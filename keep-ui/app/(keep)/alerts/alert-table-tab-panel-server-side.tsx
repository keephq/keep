import { FacetDto } from "@/features/filter";
import { AlertsQuery, AlertTableServerSide } from "./alert-table-server-side";
import { useAlertTableCols } from "./alert-table-utils";
import {
  AlertDto,
  AlertKnownKeys,
  getTabsFromPreset,
} from "@/entities/alerts/model";
import { Preset } from "@/entities/presets/model/types";

interface Props {
  refreshToken: string | null;
  initialFacets: FacetDto[];
  alerts: AlertDto[];
  alertsTotalCount: number;
  preset: Preset;
  isAsyncLoading: boolean;
  setTicketModalAlert: (alert: AlertDto | null) => void;
  setNoteModalAlert: (alert: AlertDto | null) => void;
  setRunWorkflowModalAlert: (alert: AlertDto | null) => void;
  setDismissModalAlert: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert: (alert: AlertDto | null) => void;
  mutateAlerts: () => void;
  onQueryChange?: (query: AlertsQuery) => void;
  onLiveUpdateStateChange?: (isLiveUpdateEnabled: boolean) => void;
}

export default function AlertTableTabPanelServerSide({
  refreshToken,
  initialFacets,
  alerts,
  alertsTotalCount,
  preset,
  isAsyncLoading,
  setTicketModalAlert,
  setNoteModalAlert,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  setChangeStatusAlert,
  mutateAlerts,
  onQueryChange,
  onLiveUpdateStateChange,
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
      refreshToken={refreshToken}
      initialFacets={initialFacets}
      alerts={alerts}
      alertsTotalCount={alertsTotalCount}
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
      onQueryChange={onQueryChange}
      onLiveUpdateStateChange={onLiveUpdateStateChange}
      onRefresh={() => mutateAlerts()}
    />
  );
}
