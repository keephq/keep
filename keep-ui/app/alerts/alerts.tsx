import {
  Card,
  TabGroup,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
} from "@tremor/react";
import useSWR from "swr";
import { fetcher } from "utils/fetcher";
import { AlertTable } from "./alert-table";
import { AlertDto, Preset } from "./models";
import { getApiURL } from "utils/apiUrl";
import { useEffect, useState } from "react";
import Loading from "app/loading";
import Pusher, { Channel } from "pusher-js";
import { Workflow } from "app/workflows/models";
import { ProvidersResponse } from "app/providers/providers";
import zlib from "zlib";
import "./alerts.client.css";
import { User as NextUser } from "next-auth";
import { User } from "app/settings/models";
import AlertPresets, { Option } from "./alert-presets";
import AlertActions from "./alert-actions";
import { RowSelectionState } from "@tanstack/react-table";
import AlertStreamline from "./alert-streamline";

const defaultPresets: Preset[] = [
  { name: "Feed", options: [] },
  { name: "Deleted", options: [] },
];

export default function Alerts({
  accessToken,
  tenantId,
  pusher,
  user,
  pusherDisabled,
}: {
  accessToken: string;
  tenantId: string;
  pusher: Pusher | null;
  user: NextUser;
  pusherDisabled: boolean;
}) {
  const apiUrl = getApiURL();
  const [alerts, setAlerts] = useState<AlertDto[]>([]);
  const [showDeleted, setShowDeleted] = useState<boolean>(false);
  const [isSlowLoading, setIsSlowLoading] = useState<boolean>(false);
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [selectedOptions, setSelectedOptions] = useState<Option[]>([]);
  const [lastReceivedAlertDate, setLastReceivedAlertDate] = useState<Date>();
  const [selectedPreset, setSelectedPreset] = useState<Preset | null>(
    defaultPresets[0] // Feed
  );
  const [channel, setChannel] = useState<Channel | null>(null);
  const [isAsyncLoading, setIsAsyncLoading] = useState<boolean>(true);
  const { data, isLoading, mutate } = useSWR<AlertDto[]>(
    `${apiUrl}/alerts?sync=${pusherDisabled ? "true" : "false"}`,
    (url) => fetcher(url, accessToken),
    {
      revalidateOnFocus: false,
      onLoadingSlow: () => setIsSlowLoading(true),
      loadingTimeout: 5000,
    }
  );
  const { data: workflows } = useSWR<Workflow[]>(
    `${apiUrl}/workflows`,
    (url) => fetcher(url, accessToken),
    { revalidateOnFocus: false }
  );
  const { data: providers } = useSWR<ProvidersResponse>(
    `${apiUrl}/providers`,
    (url) => fetcher(url, accessToken),
    { revalidateOnFocus: false }
  );
  const { data: users } = useSWR<User[]>(
    `${apiUrl}/settings/users`,
    (url) => fetcher(url, accessToken),
    { revalidateOnFocus: false }
  );
  const { data: presets = defaultPresets, mutate: presetsMutate } = useSWR<
    Preset[]
  >(
    `${apiUrl}/preset`,
    async (url) => {
      const data = await fetcher(url, accessToken);
      return [...defaultPresets, ...data];
    },
    { revalidateOnFocus: false }
  );

  useEffect(() => {
    if (data) {
      data.forEach(
        (alert) => (alert.lastReceived = new Date(alert.lastReceived))
      );
      setAlerts(data);
      if (pusherDisabled) setIsAsyncLoading(false);
    }
  }, [data, pusherDisabled]);

  useEffect(() => {
    if (!pusherDisabled && pusher) {
      console.log("Connecting to pusher");
      const channelName = `private-${tenantId}`;
      const pusherChannel = pusher.subscribe(channelName);
      setChannel(pusherChannel);
      pusherChannel.bind(
        "async-alerts",
        function (base64CompressedAlert: string) {
          setLastReceivedAlertDate(new Date());
          const decompressedAlert = zlib.inflateSync(
            Buffer.from(base64CompressedAlert, "base64")
          );
          const newAlerts = JSON.parse(
            new TextDecoder().decode(decompressedAlert)
          ) as AlertDto[];
          setAlerts((prevAlerts) => {
            // Create a map of the latest received times for the new alerts
            const latestReceivedTimes = new Map();
            newAlerts.forEach((alert) => {
              if (typeof alert.lastReceived === "string")
                alert.lastReceived = new Date(alert.lastReceived);
              latestReceivedTimes.set(alert.fingerprint, alert.lastReceived);
            });

            // Filter out previous alerts if they are already in the new alerts with a more recent lastReceived
            const filteredPrevAlerts = prevAlerts.filter((prevAlert) => {
              const newAlertReceivedTime = latestReceivedTimes.get(
                prevAlert.fingerprint
              );
              return (
                !newAlertReceivedTime ||
                prevAlert.lastReceived > newAlertReceivedTime
              );
            });

            // Filter out new alerts if their fingerprint is already in the filtered previous alerts
            const filteredNewAlerts = newAlerts.filter((newAlert) => {
              return !filteredPrevAlerts.some(
                (prevAlert) => prevAlert.fingerprint === newAlert.fingerprint
              );
            });

            // Combine the filtered lists
            return [...filteredNewAlerts, ...filteredPrevAlerts];
          });
        }
      );

      pusherChannel.bind("async-done", function () {
        setIsAsyncLoading(false);
      });

      setTimeout(() => setIsAsyncLoading(false), 10000); // If we don't receive any alert in 10 seconds, we assume that the async process is done (#641)

      console.log("Connected to pusher");
      return () => {
        pusher.unsubscribe(channelName);
      };
    } else {
      console.log("Pusher disabled");
    }
  }, [pusher, tenantId, pusherDisabled]);

  if (isLoading) return <Loading slowLoading={isSlowLoading} />;

  const onDelete = (
    fingerprint: string,
    lastReceived: Date,
    restore: boolean = false
  ) => {
    setAlerts((prevAlerts) =>
      prevAlerts.map((alert) => {
        if (
          alert.fingerprint === fingerprint &&
          alert.lastReceived == lastReceived
        ) {
          if (!restore) {
            alert.deleted = [lastReceived.toISOString()];
          } else {
            alert.deleted = [];
          }
          if (alert.assignees !== undefined) {
            alert.assignees[lastReceived.toISOString()] = user.email;
          } else {
            alert.assignees = { [lastReceived.toISOString()]: user.email };
          }
        }
        return alert;
      })
    );
  };

  const setAssignee = (
    fingerprint: string,
    lastReceived: Date,
    unassign: boolean // Currently unused
  ) => {
    setAlerts((prevAlerts) =>
      prevAlerts.map((alert) => {
        if (alert.fingerprint === fingerprint) {
          if (alert.assignees !== undefined) {
            alert.assignees[lastReceived.toISOString()] = user.email;
          } else {
            alert.assignees = { [lastReceived.toISOString()]: user.email };
          }
        }
        return alert;
      })
    );
  };

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
            onDelete={onDelete}
            alerts={currentStateAlerts}
          />
        ) : (
          <AlertPresets
            preset={selectedPreset}
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
          workflows={workflows}
          providers={providers?.installed_providers}
          mutate={mutate}
          isAsyncLoading={isAsyncLoading}
          onDelete={onDelete}
          setAssignee={setAssignee}
          users={users}
          currentUser={user}
          rowSelection={rowSelection}
          setRowSelection={setRowSelection}
          presetName={preset.name}
          accessToken={accessToken}
        />
      </TabPanel>
    );
  };

  function showDeletedAlert(alert: AlertDto): boolean {
    return (
      showDeleted === alert.deleted.includes(alert.lastReceived.toISOString())
    );
  }

  function filterAlerts(alert: AlertDto): boolean {
    if (selectedOptions.length === 0) {
      return true;
    }
    return selectedOptions.every((option) => {
      const optionSplit = option.value.split("=");
      const key = optionSplit[0];
      const value = optionSplit[1]?.toLowerCase();
      if (key === "source") {
        return alert.source?.every((v) => value.split(",").includes(v));
      } else if (typeof value === "string") {
        return ((alert as any)[key] as string)?.toLowerCase().includes(value);
      }
      return false;
    });
  }

  const currentStateAlerts = alerts
    .filter((alert) => showDeletedAlert(alert) && filterAlerts(alert))
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
    <>
      <Card className="mt-10 p-4 md:p-10 mx-auto">
        {!pusherDisabled && (
          <AlertStreamline
            channel={channel}
            lastReceivedAlertDate={lastReceivedAlertDate}
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
    </>
  );
}
