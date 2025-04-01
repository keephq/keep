import { FacetDto } from "@/features/filter";
import { AlertTableServerSide } from "@/widgets/alerts-table/ui/alert-table-server-side";
import { useAlertTableCols } from "@/widgets/alerts-table/lib/alert-table-utils";
import {
  AlertDto,
  AlertKnownKeys,
  AlertsQuery,
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
  queryTimeInSeconds: number;
  setTicketModalAlert: (alert: AlertDto | null) => void;
  setNoteModalAlert: (alert: AlertDto | null) => void;
  setRunWorkflowModalAlert: (alert: AlertDto | null) => void;
  setDismissModalAlert: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert: (alert: AlertDto | null) => void;
  mutateAlerts: () => void;
  onReload?: (query: AlertsQuery) => void;
  onPoll?: () => void;
  onQueryChange?: () => void;
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
  onReload,
  onPoll,
  onQueryChange,
  onLiveUpdateStateChange,
  queryTimeInSeconds,
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
      presetTabs={presetTabs}
      queryTimeInSeconds={queryTimeInSeconds}
      mutateAlerts={mutateAlerts}
      setRunWorkflowModalAlert={setRunWorkflowModalAlert}
      setDismissModalAlert={setDismissModalAlert}
      setChangeStatusAlert={setChangeStatusAlert}
      onReload={onReload}
      onPoll={onPoll}
      onQueryChange={onQueryChange}
      onLiveUpdateStateChange={onLiveUpdateStateChange}
    />
  );
}
