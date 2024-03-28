import { useMemo, useState } from "react";
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
import AlertRunWorkflowModal from "./alert-run-workflow-modal";
import AlertDismissModal from "./alert-dismiss-modal";

const defaultPresets: Preset[] = [
  { id: "feed", name: "feed", options: [], is_private: false },
  { id: "deleted", name: "deleted", options: [], is_private: false },
  { id: "dismissed", name: "dismissed", options: [], is_private: false },
  { id: "groups", name: "groups", options: [], is_private: false },
];

type AlertsProps = {
  presetName: string;
};

export default function Alerts({ presetName }: AlertsProps) {
  const { useAllAlertsWithSubscription } = useAlerts();

  const { data: providersData = { installed_providers: [] } } = useProviders();

  const ticketingProviders = useMemo(
    () =>
      providersData.installed_providers.filter((provider) =>
        provider.tags.includes("ticketing")
      ),
    [providersData.installed_providers]
  );
  // hooks for the note and ticket modals
  const [noteModalAlert, setNoteModalAlert] = useState<AlertDto | null>();
  const [ticketModalAlert, setTicketModalAlert] = useState<AlertDto | null>();
  const [runWorkflowModalAlert, setRunWorkflowModalAlert] =
    useState<AlertDto | null>();
  const [dismissModalAlert, setDismissModalAlert] = useState<AlertDto | null>();

  const { useAllPresets } = usePresets();

  const { data: alerts, isAsyncLoading } = useAllAlertsWithSubscription();

  const { data: savedPresets = [] } = useAllPresets({
    revalidateOnFocus: false,
  });
  const presets = [...defaultPresets, ...savedPresets] as const;

  const selectedPreset = presets.find(
    (preset) => preset.name.toLowerCase() === decodeURIComponent(presetName)
  );

  if (selectedPreset === undefined) {
    return null;
  }

  return (
    <>
      <AlertTableTabPanel
        key={selectedPreset.name}
        preset={selectedPreset}
        alerts={alerts}
        isAsyncLoading={isAsyncLoading}
        setTicketModalAlert={setTicketModalAlert}
        setNoteModalAlert={setNoteModalAlert}
        setRunWorkflowModalAlert={setRunWorkflowModalAlert}
        setDismissModalAlert={setDismissModalAlert}
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
      <AlertRunWorkflowModal
        alert={runWorkflowModalAlert}
        handleClose={() => setRunWorkflowModalAlert(null)}
      />
      <AlertDismissModal
        alert={dismissModalAlert}
        handleClose={() => setDismissModalAlert(null)}
      />
    </>
  );
}
