"use client";

import { useEffect, useMemo, useState } from "react";
import { useAlerts } from "utils/hooks/useAlerts";
import { usePresets } from "@/entities/presets/model/usePresets";
import AlertTableTabPanel from "./alert-table-tab-panel";
import { AlertHistory } from "./alert-history";
import AlertAssignTicketModal from "./alert-assign-ticket-modal";
import AlertNoteModal from "./alert-note-modal";
import { useProviders } from "utils/hooks/useProviders";
import { AlertDto } from "./models";
import { AlertMethodModal } from "./alert-method-modal";
import ManualRunWorkflowModal from "@/app/(keep)/workflows/manual-run-workflow-modal";
import AlertDismissModal from "./alert-dismiss-modal";
import { ViewAlertModal } from "./ViewAlertModal";
import { useRouter, useSearchParams } from "next/navigation";
import AlertChangeStatusModal from "./alert-change-status-modal";
import { useAlertPolling } from "utils/hooks/usePusher";
import NotFound from "@/app/(keep)/not-found";
import { useApi } from "@/shared/lib/hooks/useApi";
import EnrichAlertSidePanel from "@/app/(keep)/alerts/EnrichAlertSidePanel";
import Loading from "../loading";
import { Preset } from "@/entities/presets/model/types";

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
  presetName: string;
};

export default function Alerts({ presetName }: AlertsProps) {
  const { usePresetAlerts } = useAlerts();
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
  const { dynamicPresets: savedPresets = [], isLoading: isPresetsLoading } =
    usePresets({
      revalidateOnFocus: false,
    });
  const presets = [...defaultPresets, ...savedPresets] as const;

  const selectedPreset = presets.find(
    (preset) => preset.name.toLowerCase() === decodeURIComponent(presetName)
  );

  const { data: pollAlerts } = useAlertPolling();
  const {
    data: alerts = [],
    isLoading: isAsyncLoading,
    mutate: mutateAlerts,
    error: alertsError,
  } = usePresetAlerts(selectedPreset ? selectedPreset.name : "");

  const api = useApi();
  const isLoading = isAsyncLoading || !api.isReady();

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

  useEffect(() => {
    if (pollAlerts) {
      mutateAlerts();
    }
  }, [mutateAlerts, pollAlerts]);

  if (!selectedPreset && isPresetsLoading) {
    return <Loading />;
  }
  if (!selectedPreset) {
    return <NotFound />;
  }

  return (
    <>
      <AlertTableTabPanel
        key={selectedPreset.name}
        preset={selectedPreset}
        alerts={alerts}
        isAsyncLoading={isLoading}
        setTicketModalAlert={setTicketModalAlert}
        setNoteModalAlert={setNoteModalAlert}
        setRunWorkflowModalAlert={setRunWorkflowModalAlert}
        setDismissModalAlert={setDismissModalAlert}
        setChangeStatusAlert={setChangeStatusAlert}
        mutateAlerts={mutateAlerts}
      />

      {selectedPreset && (
        <AlertHistory alerts={alerts} presetName={selectedPreset.name} />
      )}
      <AlertAssignTicketModal
        handleClose={() => setTicketModalAlert(null)}
        ticketingProviders={ticketingProviders}
        alert={ticketModalAlert ?? null}
      />
      <AlertNoteModal
        handleClose={() => setNoteModalAlert(null)}
        alert={noteModalAlert ?? null}
      />
      {selectedPreset && <AlertMethodModal presetName={selectedPreset.name} />}
      <ManualRunWorkflowModal
        alert={runWorkflowModalAlert}
        handleClose={() => setRunWorkflowModalAlert(null)}
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
