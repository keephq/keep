"use client";

import { useEffect, useMemo, useState } from "react";
import { Preset } from "./models";
import { useAlerts } from "utils/hooks/useAlerts";
import { usePresets } from "utils/hooks/usePresets";
import AlertTableTabPanel from "./alert-table-tab-panel";
import { AlertHistory } from "./alert-history";
import AlertAssignTicketModal from "./alert-assign-ticket-modal";
import AlertNoteModal from "./alert-note-modal";
import { useProviders } from "utils/hooks/useProviders";
import { AlertDto } from "./models";
import { AlertMethodModal } from "./alert-method-modal";
import ManualRunWorkflowModal from "@/app/workflows/manual-run-workflow-modal";
import AlertDismissModal from "./alert-dismiss-modal";
import { ViewAlertModal } from "./ViewAlertModal";
import { useRouter, useSearchParams } from "next/navigation";
import AlertChangeStatusModal from "./alert-change-status-modal";
import { useAlertPolling } from "utils/hooks/usePusher";
import NotFound from "@/app/not-found";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";

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
  {
    id: "dismissed",
    name: "dismissed",
    options: [],
    is_private: false,
    is_noisy: false,
    alerts_count: 0,
    should_do_noise_now: false,
    tags: [],
  },
  {
    id: "groups",
    name: "groups",
    options: [],
    is_private: false,
    is_noisy: false,
    alerts_count: 0,
    should_do_noise_now: false,
    tags: [],
  },
  {
    id: "without-incident",
    name: "without-incident",
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
  const { useAllPresets } = usePresets();

  const { data: savedPresets = [] } = useAllPresets({
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

  const { status: sessionStatus } = useSession();
  const isLoading = isAsyncLoading || sessionStatus === "loading";

  useEffect(() => {
    const fingerprint = searchParams?.get("alertPayloadFingerprint");
    if (fingerprint) {
      const alert = alerts?.find((alert) => alert.fingerprint === fingerprint);
      setViewAlertModal(alert);
    } else {
      setViewAlertModal(null);
    }
  }, [searchParams, alerts]);

  useEffect(() => {
    if (pollAlerts) {
      mutateAlerts();
    }
  }, [mutateAlerts, pollAlerts]);

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
    </>
  );
}
