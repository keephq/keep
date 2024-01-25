import { Card, TabGroup, TabList, Tab, TabPanels } from "@tremor/react";
import { Preset } from "./models";
import { useMemo } from "react";
import "./alerts.client.css";
import AlertStreamline from "./alert-streamline";
import {
  getDefaultSubscriptionObj,
  getFormatAndMergePusherWithEndpointAlerts,
  useAlerts,
} from "utils/hooks/useAlerts";
import { usePresets } from "utils/hooks/usePresets";
import AlertTableTabPanel from "./alert-table-tab-panel";
import { AlertHistory } from "./alert-history";

const defaultPresets: Preset[] = [
  { name: "Feed", options: [] },
  { name: "Deleted", options: [] },
  { name: "Groups", options: [] },
];

export default function Alerts() {
  const { useAllAlerts, useAllAlertsWithSubscription } = useAlerts();

  const { data: endpointAlerts = [] } = useAllAlerts({
    revalidateOnFocus: false,
  });

  const { data: alertSubscription = getDefaultSubscriptionObj(true) } =
    useAllAlertsWithSubscription();
  const {
    alerts: pusherAlerts,
    isAsyncLoading,
    lastSubscribedDate,
    pusherChannel,
  } = alertSubscription;

  const { data: savedPresets = [] } = usePresets({
    revalidateOnFocus: false,
  });
  const presets = [...defaultPresets, ...savedPresets] as const;

  const alerts = useMemo(
    () =>
      getFormatAndMergePusherWithEndpointAlerts(endpointAlerts, pusherAlerts),
    [endpointAlerts, pusherAlerts]
  );

  return (
    <Card className="mt-10 p-4 md:p-10 mx-auto">
      {pusherChannel && (
        <AlertStreamline
          pusherChannel={pusherChannel}
          lastSubscribedDate={lastSubscribedDate}
        />
      )}
      {/* key is necessary to re-render tabs on preset delete */}
      <TabGroup key={presets.length}>
        <TabList variant="line" color="orange">
          {presets.map((preset, index) => (
            <Tab key={preset.name} tabIndex={index}>
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
            />
          ))}
        </TabPanels>
        <AlertHistory alerts={alerts} />
      </TabGroup>
    </Card>
  );
}
