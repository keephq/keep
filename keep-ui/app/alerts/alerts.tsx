import { Card, TabGroup, TabList, Tab, TabPanels } from "@tremor/react";
import { Preset } from "./models";
import { useMemo, useState } from "react";
import "./alerts.client.css";
import AlertStreamline from "./alert-streamline";
import { useAlerts } from "utils/hooks/useAlerts";
import { usePresets } from "utils/hooks/usePresets";
import AlertTableTabPanel from "./alert-table-tab-panel";
import { AlertHistory } from "./alert-history";
import { usePathname, useRouter } from "next/navigation";
import AlertAssignTicketModal from "./alert-assign-ticket-modal";
import AlertNoteModal from "./alert-note-modal";
import { useProviders } from "utils/hooks/useProviders";
import { AlertDto } from "./models";
import { AlertMethodModal } from "./alert-method-modal";
import AlertRunWorkflowModal from "./alert-run-workflow-modal";

const defaultPresets: Preset[] = [
  { name: "Feed", options: [] },
  { name: "Deleted", options: [] },
  { name: "Groups", options: [] },
];

export default function Alerts() {
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

  const { useAllPresets, getCurrentPreset } = usePresets();
  const pathname = usePathname();
  const router = useRouter();
  const currentSelectedPreset = getCurrentPreset();

  const {
    data: alerts,
    isAsyncLoading,
    lastSubscribedDate,
    pusherChannel,
  } = useAllAlertsWithSubscription();

  const { data: savedPresets = [] } = useAllPresets({
    revalidateOnFocus: false,
  });
  const presets = [...defaultPresets, ...savedPresets] as const;

  const selectPreset = (presetName: string) => {
    router.replace(`${pathname}?selectedPreset=${presetName}`);
  };

  const selectedPresetIndex =
    presets.findIndex((preset) => preset.name === currentSelectedPreset) ?? 0;

  return (
    <Card className="mt-10 p-4 md:p-10 mx-auto">
      {pusherChannel && (
        <AlertStreamline
          pusherChannel={pusherChannel}
          lastSubscribedDate={lastSubscribedDate}
        />
      )}
      {/* key is necessary to re-render tabs on preset delete */}
      <TabGroup key={presets.length} index={selectedPresetIndex}>
        <TabList variant="line" color="orange">
          {presets.map((preset, index) => (
            <Tab
              key={preset.name}
              tabIndex={index}
              onClick={() => selectPreset(preset.name)}
            >
              {preset.name}
            </Tab>
          ))}
        </TabList>
        <TabPanels>
          {presets.map((preset) => (
            <AlertTableTabPanel
              key={preset.name}
              preset={preset}
              alerts={alerts}
              isAsyncLoading={isAsyncLoading}
              setTicketModalAlert={setTicketModalAlert}
              setNoteModalAlert={setNoteModalAlert}
              setRunWorkflowModalAlert={setRunWorkflowModalAlert}
            />
          ))}
        </TabPanels>
        <AlertHistory alerts={alerts} />
        <AlertAssignTicketModal
          handleClose={() => setTicketModalAlert(null)}
          ticketingProviders={ticketingProviders}
          alert={ticketModalAlert ?? null}
        />
        <AlertNoteModal
          handleClose={() => setNoteModalAlert(null)}
          alert={noteModalAlert ?? null}
        />
        <AlertMethodModal />
        <AlertRunWorkflowModal
          alert={runWorkflowModalAlert}
          handleClose={() => setRunWorkflowModalAlert(null)}
        />
      </TabGroup>
    </Card>
  );
}
