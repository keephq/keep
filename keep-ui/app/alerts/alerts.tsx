import {
  Card,
  TabGroup,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
} from "@tremor/react";
import { AlertTable } from "./alert-table";
import { AlertDto, Preset } from "./models";
import { useMemo, useState } from "react";
import Loading from "app/loading";
import "./alerts.client.css";
import AlertPresets, { Option } from "./alert-presets";
import AlertActions from "./alert-actions";
import { RowSelectionState } from "@tanstack/react-table";
import AlertStreamline from "./alert-streamline";
import {
  getDefaultSubscriptionObj,
  getFormatAndMergePusherWithEndpointAlerts,
  useAlerts,
} from "utils/hooks/useAlerts";
import { usePresets } from "utils/hooks/usePresets";

const defaultPresets: Preset[] = [
  { name: "Feed", options: [] },
  { name: "Deleted", options: [] },
];

interface Props {
  accessToken: string;
}

export default function Alerts({ accessToken }: Props) {
  const [showDeleted, setShowDeleted] = useState<boolean>(false);
  const [isSlowLoading, setIsSlowLoading] = useState<boolean>(false);
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [selectedOptions, setSelectedOptions] = useState<Option[]>([]);

  const [selectedPreset, setSelectedPreset] = useState<Preset | null>(
    defaultPresets[0] // Feed
  );
  const { useAllAlerts, useAllAlertsWithSubscription } = useAlerts();

  const { data: endpointAlerts = [], isLoading } = useAllAlerts({
    revalidateOnFocus: false,
    onLoadingSlow: () => setIsSlowLoading(true),
    loadingTimeout: 5000,
  });

  const { data: alertSubscription = getDefaultSubscriptionObj(true) } =
    useAllAlertsWithSubscription();
  const {
    alerts: pusherAlerts,
    isAsyncLoading,
    lastSubscribedDate,
    pusherChannel,
  } = alertSubscription;

  const { data: savedPresets = [], mutate: presetsMutate } = usePresets({
    revalidateOnFocus: false,
  });
  const presets: Preset[] = [...defaultPresets, ...savedPresets];

  const alerts = useMemo(
    () =>
      getFormatAndMergePusherWithEndpointAlerts(endpointAlerts, pusherAlerts),
    [endpointAlerts, pusherAlerts]
  );

  if (isLoading) return <Loading slowLoading={isSlowLoading} />;

  const AlertTableTabPanel = ({ preset }: { preset: Preset }) => {
    const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
    const selectedRowIds = Object.entries(rowSelection).reduce<string[]>(
      (acc, [alertId, isSelected]) => {
        if (isSelected) {
          return acc.concat(alertId);
        }
        return acc;
      },
      []
    );

    return (
      <TabPanel className="mt-4">
        {selectedRowIds.length ? (
          <AlertActions
            selectedRowIds={selectedRowIds}
            alerts={currentStateAlerts}
          />
        ) : (
          <AlertPresets
            preset={preset}
            alerts={currentStateAlerts}
            selectedOptions={selectedOptions}
            setSelectedOptions={setSelectedOptions}
            accessToken={accessToken}
            presetsMutator={() => {
              onIndexChange(0);
              presetsMutate();
            }}
            isLoading={isAsyncLoading}
          />
        )}
        <AlertTable
          alerts={currentStateAlerts}
          isAsyncLoading={isAsyncLoading}
          rowSelection={rowSelection}
          setRowSelection={setRowSelection}
          presetName={preset.name}
        />
      </TabPanel>
    );
  };

  function showDeletedAlert(alert: AlertDto): boolean {
    return (
      showDeleted === alert.deleted.includes(alert.lastReceived.toISOString())
    );
  }

  const getPresetAlerts = (alert: AlertDto, preset: Preset): boolean => {
    if (selectedOptions.length === 0) {
      return true;
    }

    if (preset.name === "Deleted") {
      return alert.deleted.includes(alert.lastReceived.toISOString());
    }

    return preset.options.every((option) => {
      const [key, value] = option.value.split("=");

      if (key && value) {
        const lowercaseKey = key.toLowerCase() as keyof AlertDto;
        const lowercaseValue = value.toLowerCase();

        const alertValue = alert[lowercaseKey];

        if (Array.isArray(alertValue)) {
          return alertValue.every((v) => lowercaseValue.split(",").includes(v));
        }

        if (typeof alertValue === "string") {
          return alertValue.toLowerCase().includes(lowercaseValue);
        }
      }

      return false;
    });
  };

  const currentStateAlerts = alerts
    .filter((alert) => getPresetAlerts(alert, selectedPreset))
    .sort((a, b) => b.lastReceived.getTime() - a.lastReceived.getTime());

  function onIndexChange(index: number) {
    setTabIndex(index);
    const preset = presets![index];
    if (preset.name === "Deleted") {
      setShowDeleted(true);
    } else {
      setShowDeleted(false);
    }
    setSelectedOptions(preset.options);
    setSelectedPreset(preset);
  }

  return (
    <Card className="mt-10 p-4 md:p-10 mx-auto">
      {pusherChannel && (
        <AlertStreamline
          pusherChannel={pusherChannel}
          lastSubscribedDate={lastSubscribedDate}
        />
      )}
      <TabGroup onIndexChange={onIndexChange} index={tabIndex}>
        <TabList variant="line" color="orange">
          {presets.map((preset, index) => (
            <Tab key={preset.name} tabIndex={index}>
              {preset.name}
            </Tab>
          ))}
        </TabList>
        <TabPanels>
          {presets.map((preset) => (
            <AlertTableTabPanel key={preset.name} preset={preset} />
          ))}
        </TabPanels>
      </TabGroup>
    </Card>
  );
}
