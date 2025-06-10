"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { type AlertDto, type AlertsQuery } from "@/entities/alerts/model";
import { usePresets, type Preset } from "@/entities/presets/model";
import { AlertHistoryModal } from "@/features/alerts/alert-history";
import { AlertAssignTicketModal } from "@/features/alerts/alert-assign-ticket";
import { AlertNoteModal } from "@/features/alerts/alert-note";
import { AlertMethodModal } from "@/features/alerts/alert-call-provider-method";
import { ManualRunWorkflowModal } from "@/features/workflows/manual-run-workflow";
import { AlertDismissModal } from "@/features/alerts/dismiss-alert";
import { ViewAlertModal } from "@/features/alerts/view-raw-alert";
import { AlertChangeStatusModal } from "@/features/alerts/alert-change-status";
import { EnrichAlertSidePanel } from "@/features/alerts/enrich-alert";
import { FacetDto } from "@/features/filter";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepLoader, showErrorToast } from "@/shared/ui";
import NotFound from "@/app/(keep)/not-found";
import AlertTableTabPanelServerSide from "./alert-table-tab-panel-server-side";
import { useProviders } from "@/utils/hooks/useProviders";
import {
  useAlertsTableData,
  AlertsTableDataQuery,
} from "@/widgets/alerts-table/ui/useAlertsTableData";

const defaultPresets: Preset[] = [
  {
    id: "feed",
    name: "feed",
    options: [],
    is_private: false,
    is_noisy: false,
    alerts_count: 0,
    should_do_noise_now: false,
    tags: [],
    counter_shows_firing_only: false,
  },
];

type AlertsProps = {
  initialFacets: FacetDto[];
  presetName: string;
};

export default function Alerts({ presetName, initialFacets }: AlertsProps) {
  const api = useApi();
  const [alertsQueryState, setAlertsQueryState] = useState<
    AlertsQuery | undefined
  >();
  const [alertsTableDataQuery, setAlertsTableDataQuery] =
    useState<AlertsTableDataQuery>();
  const { data: providersData = { installed_providers: [] } } = useProviders();
  const router = useRouter();

  const ticketingProviders = useMemo(
    () =>
      providersData.installed_providers.filter((provider) =>
        provider.tags.includes("ticketing")
      ),
    [providersData.installed_providers]
  );

  const searchParams = useSearchParams();
  // hooks for the note and ticket modals
  const [noteModalAlert, setNoteModalAlert] = useState<AlertDto | null>();
  const [ticketModalAlert, setTicketModalAlert] = useState<AlertDto | null>();
  const [runWorkflowModalAlert, setRunWorkflowModalAlert] =
    useState<AlertDto | null>();
  const [dismissModalAlert, setDismissModalAlert] = useState<
    AlertDto[] | null
  >();
  const [changeStatusAlert, setChangeStatusAlert] = useState<AlertDto | null>();
  const [viewAlertModal, setViewAlertModal] = useState<AlertDto | null>();
  const [viewEnrichAlertModal, setEnrichAlertModal] =
    useState<AlertDto | null>();
  const [isEnrichSidebarOpen, setIsEnrichSidebarOpen] = useState(false);
  const { dynamicPresets: savedPresets = [], isLoading: _isPresetsLoading } =
    usePresets({
      revalidateOnFocus: false,
    });
  const isPresetsLoading = _isPresetsLoading || !api.isReady();
  const presets = [...defaultPresets, ...savedPresets] as const;

  const selectedPreset = presets.find(
    (preset) => preset.name.toLowerCase() === decodeURIComponent(presetName)
  );

  const {
    alerts,
    alertsLoading,
    mutateAlerts,
    alertsError: alertsError,
    totalCount,
    facetsCel,
    facetsPanelRefreshToken,
    refreshFacets,
  } = useAlertsTableData(alertsTableDataQuery);

  useEffect(() => {
    const fingerprint = searchParams?.get("alertPayloadFingerprint");
    const enrich = searchParams?.get("enrich");
    if (fingerprint && enrich && alerts) {
      const alert = alerts?.find((alert) => alert.fingerprint === fingerprint);
      if (alert) {
        setEnrichAlertModal(alert);
        setIsEnrichSidebarOpen(true);
      } else {
        showErrorToast(null, "Alert fingerprint not found");
        resetUrlAfterModal();
      }
    } else if (fingerprint && alerts) {
      const alert = alerts?.find((alert) => alert.fingerprint === fingerprint);
      if (alert) {
        setViewAlertModal(alert);
      } else {
        showErrorToast(null, "Alert fingerprint not found");
        resetUrlAfterModal();
      }
    } else if (alerts) {
      setViewAlertModal(null);
      setEnrichAlertModal(null);
      setIsEnrichSidebarOpen(false);
    }
  }, [searchParams, alerts]);

  const alertsQueryStateRef = useRef(alertsQueryState);

  const reloadAlerts = useCallback(
    (alertsQuery: AlertsQuery) => {
      // if the query is the same as the last one, just refetch
      if (
        JSON.stringify(alertsQuery) ===
        JSON.stringify(alertsQueryStateRef.current)
      ) {
        mutateAlerts();
        return;
      }

      // if the query is different, update the state
      setAlertsQueryState(alertsQuery);
      alertsQueryStateRef.current = alertsQuery;
    },
    [setAlertsQueryState]
  );

  const resetUrlAfterModal = useCallback(() => {
    const currentParams = new URLSearchParams(window.location.search);
    Array.from(currentParams.keys())
      .filter((paramKey) => paramKey !== "cel")
      .forEach((paramKey) => currentParams.delete(paramKey));
    let url = `${window.location.pathname}`;

    if (currentParams.toString()) {
      url += `?${currentParams.toString()}`;
    }

    router.replace(url);
  }, [router]);

  // if we don't have presets data yet, just show loading
  if (!selectedPreset && isPresetsLoading) {
    return <KeepLoader />;
  }

  // if we have an error, throw it, error.tsx will catch it
  if (alertsError) {
    throw alertsError;
  }

  if (!selectedPreset) {
    return <NotFound />;
  }

  return (
    <>
      <AlertTableTabPanelServerSide
        initialFacets={initialFacets}
        key={selectedPreset.name}
        facetsPanelRefreshToken={facetsPanelRefreshToken}
        preset={selectedPreset}
        alerts={alerts || []}
        alertsTotalCount={totalCount}
        facetsCel={facetsCel}
        isAsyncLoading={alertsLoading}
        setTicketModalAlert={setTicketModalAlert}
        setNoteModalAlert={setNoteModalAlert}
        setRunWorkflowModalAlert={setRunWorkflowModalAlert}
        setDismissModalAlert={setDismissModalAlert}
        setChangeStatusAlert={setChangeStatusAlert}
        mutateAlerts={mutateAlerts}
        refreshFacets={refreshFacets}
        onReload={reloadAlerts}
        onQueryChange={setAlertsTableDataQuery}
      />
      <AlertHistoryModal
        alerts={alerts || []}
        presetName={selectedPreset.name}
        onClose={resetUrlAfterModal}
      />
      <AlertDismissModal
        alert={dismissModalAlert}
        preset={selectedPreset.name}
        handleClose={() => setDismissModalAlert(null)}
      />
      <AlertChangeStatusModal
        alert={changeStatusAlert}
        presetName={selectedPreset.name}
        handleClose={() => setChangeStatusAlert(null)}
      />
      <AlertMethodModal
        alerts={alerts || []}
        presetName={selectedPreset.name}
      />
      <AlertAssignTicketModal
        handleClose={() => setTicketModalAlert(null)}
        ticketingProviders={ticketingProviders}
        alert={ticketModalAlert ?? null}
      />
      <AlertNoteModal
        handleClose={() => setNoteModalAlert(null)}
        alert={noteModalAlert ?? null}
      />
      <ManualRunWorkflowModal
        alert={runWorkflowModalAlert}
        onClose={() => setRunWorkflowModalAlert(null)}
      />
      <ViewAlertModal
        alert={viewAlertModal}
        handleClose={() => resetUrlAfterModal()}
        mutate={mutateAlerts}
      />
      <EnrichAlertSidePanel
        alert={viewEnrichAlertModal}
        isOpen={isEnrichSidebarOpen}
        handleClose={() => {
          setIsEnrichSidebarOpen(false);
          resetUrlAfterModal();
        }}
        mutate={mutateAlerts}
      />
    </>
  );
}
