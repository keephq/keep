"use client";

import { useEffect, useMemo, useState } from "react";
import { useAlerts } from "utils/hooks/useAlerts";
import { usePresets } from "@/entities/presets/model/usePresets";
import { AlertHistory } from "./alert-history";
import AlertAssignTicketModal from "./alert-assign-ticket-modal";
import AlertNoteModal from "./alert-note-modal";
import { useProviders } from "utils/hooks/useProviders";
import { AlertDto } from "@/entities/alerts/model";
import { AlertMethodModal } from "./alert-method-modal";
import ManualRunWorkflowModal from "@/app/(keep)/workflows/manual-run-workflow-modal";
import AlertDismissModal from "./alert-dismiss-modal";
import { ViewAlertModal } from "./ViewAlertModal";
import { useRouter, useSearchParams } from "next/navigation";
import AlertChangeStatusModal from "./alert-change-status-modal";
import NotFound from "@/app/(keep)/not-found";
import { useApi } from "@/shared/lib/hooks/useApi";
import EnrichAlertSidePanel from "@/app/(keep)/alerts/EnrichAlertSidePanel";
import Loading from "../loading";
import { Preset } from "@/entities/presets/model/types";
import { useAlertPolling } from "@/utils/hooks/useAlertPolling";
import AlertTableTabPanelServerSide from "./alert-table-tab-panel-server-side";
import { AlertsQuery } from "./alert-table-server-side";
import { FacetDto } from "@/features/filter";
import { v4 as uuidV4 } from "uuid";

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
  const [isLiveUpdateEnabled, setIsLiveUpdateEnabled] = useState(false);
  const [alerts, setAlerts] = useState<AlertDto[] | undefined>(undefined);
  const { useLastAlerts } = useAlerts();
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
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
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

  const { data: pollAlerts } = useAlertPolling(isLiveUpdateEnabled);
  const {
    data: fetchedAlerts = [],
    totalCount,
    isLoading: isAsyncLoading,
    mutate: mutateAlerts,
    error: alertsError,
  } = useLastAlerts(
    alertsQueryState?.cel,
    alertsQueryState?.limit,
    alertsQueryState?.offset,
    alertsQueryState?.sortBy,
    alertsQueryState?.sortDirection
  );

  useEffect(() => {
    if (isLiveUpdateEnabled) {
      if (!isAsyncLoading) {
        setAlerts(fetchedAlerts);
      }

      return;
    }

    setAlerts(isAsyncLoading ? undefined : fetchedAlerts);
  }, [isLiveUpdateEnabled, isAsyncLoading, fetchedAlerts]);

  useEffect(() => {
    const fingerprint = searchParams?.get("alertPayloadFingerprint");
    const enrich = searchParams?.get("enrich");
    if (fingerprint && enrich) {
      const alert = alerts?.find((alert) => alert.fingerprint === fingerprint);
      setEnrichAlertModal(alert);
      setIsEnrichSidebarOpen(true);
    } else if (fingerprint) {
      const alert = alerts?.find((alert) => alert.fingerprint === fingerprint);
      setViewAlertModal(alert);
    } else {
      setViewAlertModal(null);
      setEnrichAlertModal(null);
      setIsEnrichSidebarOpen(false);
    }
  }, [searchParams, alerts]);

  useEffect(
    function setNewRefreshToken() {
      if (pollAlerts) {
        setRefreshToken(uuidV4());
      }
    },
    [setRefreshToken, pollAlerts]
  );

  // if we don't have presets data yet, just show loading
  if (!selectedPreset && isPresetsLoading) {
    return <Loading />;
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
        refreshToken={refreshToken}
        preset={selectedPreset}
        alerts={alerts || []}
        alertsTotalCount={totalCount}
        isAsyncLoading={!alerts}
        setTicketModalAlert={setTicketModalAlert}
        setNoteModalAlert={setNoteModalAlert}
        setRunWorkflowModalAlert={setRunWorkflowModalAlert}
        setDismissModalAlert={setDismissModalAlert}
        setChangeStatusAlert={setChangeStatusAlert}
        mutateAlerts={mutateAlerts}
        onQueryChange={(alertsQuery) => setAlertsQueryState(alertsQuery)}
        onLiveUpdateStateChange={setIsLiveUpdateEnabled}
      />
      <AlertHistory alerts={alerts || []} presetName={selectedPreset.name} />
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
        handleClose={() => setRunWorkflowModalAlert(null)}
      />
      <ViewAlertModal
        alert={viewAlertModal}
        handleClose={() => router.replace(`/alerts/${presetName}`)}
        mutate={mutateAlerts}
      />
      <EnrichAlertSidePanel
        alert={viewEnrichAlertModal}
        isOpen={isEnrichSidebarOpen}
        handleClose={() => {
          setIsEnrichSidebarOpen(false);
          router.replace(`/alerts/${presetName}`);
        }}
        mutate={mutateAlerts}
      />
    </>
  );
}
