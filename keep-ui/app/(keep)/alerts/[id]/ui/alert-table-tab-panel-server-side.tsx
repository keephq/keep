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
import { AlertsTableDataQuery } from "@/widgets/alerts-table/ui/useAlertsTableData";

interface Props {
  initialFacets: FacetDto[];
  alerts: AlertDto[];
  alertsTotalCount: number;
  facetsCel: string | null;
  facetsPanelRefreshToken: string | undefined;
  preset: Preset;
  isAsyncLoading: boolean;
  setTicketModalAlert: (alert: AlertDto | null) => void;
  setNoteModalAlert: (alert: AlertDto | null) => void;
  setRunWorkflowModalAlert: (alert: AlertDto | null) => void;
  setDismissModalAlert: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert: (alert: AlertDto | null) => void;
  mutateAlerts: () => void;
  refreshFacets?: () => void;
  onReload?: (query: AlertsQuery) => void;
  onQueryChange?: (query: AlertsTableDataQuery) => void;
}

export default function AlertTableTabPanelServerSide({
  initialFacets,
  alerts,
  alertsTotalCount,
  preset,
  facetsCel,
  facetsPanelRefreshToken,
  isAsyncLoading,
  setTicketModalAlert,
  setNoteModalAlert,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  setChangeStatusAlert,
  mutateAlerts,
  refreshFacets,
  onReload,
  onQueryChange,
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
      facetsCel={facetsCel}
      facetsPanelRefreshToken={facetsPanelRefreshToken}
      initialFacets={initialFacets}
      alerts={alerts}
      alertsTotalCount={alertsTotalCount}
      columns={alertTableColumns}
      setDismissedModalAlert={setDismissModalAlert}
      isAsyncLoading={isAsyncLoading}
      presetName={preset.name}
      presetTabs={presetTabs}
      mutateAlerts={mutateAlerts}
      refreshFacets={refreshFacets}
      setRunWorkflowModalAlert={setRunWorkflowModalAlert}
      setDismissModalAlert={setDismissModalAlert}
      setChangeStatusAlert={setChangeStatusAlert}
      onReload={onReload}
      onQueryChange={onQueryChange}
    />
  );
}
