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
import Pusher from "pusher-js";
import { Workflow } from "app/workflows/models";
import { ProvidersResponse } from "app/providers/providers";
import zlib from "zlib";
import "./alerts.client.css";
import { User as NextUser } from "next-auth";
import { User } from "app/settings/models";
import AlertPagination from "./alert-pagination";
import AlertPresets, { Option } from "./alert-presets";
import { AlertHistory } from "./alert-history";

const defaultPresets: Preset[] = [
  { name: "Feed", options: [] },
  { name: "Deleted", options: [] },
];
const groupBy = "fingerprint"; // TODO: in the future, we'll allow to modify this

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
  const [showDeleted, setShowDeleted] = useState<boolean>(false);
  const [isSlowLoading, setIsSlowLoading] = useState<boolean>(false);
  const [startIndex, setStartIndex] = useState<number>(0);
  const [endIndex, setEndIndex] = useState<number>(0);
  const [alerts, setAlerts] = useState<AlertDto[]>([]);
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [aggregatedAlerts, setAggregatedAlerts] = useState<AlertDto[]>([]);
  const [selectedOptions, setSelectedOptions] = useState<Option[]>([]);
  const [selectedAlertHistory, setSelectedAlertHistory] = useState<AlertDto[]>(
    []
  );
  const [isOpen, setIsOpen] = useState(false);

  const closeModal = (): any => setIsOpen(false);
  const openModal = (alert: AlertDto): any => {
    setSelectedAlertHistory(groupedByAlerts[(alert as any)[groupBy!]]);
    setIsOpen(true);
  };
  const [selectedPreset, setSelectedPreset] = useState<Preset | null>(
    defaultPresets[0] // Feed
  );
  const [groupedByAlerts, setGroupedByAlerts] = useState<{
    [key: string]: AlertDto[];
  }>({});
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
  const { data: presets, mutate: presetsMutate } = useSWR<Preset[]>(
    `${apiUrl}/preset`,
    async (url) => {
      const data = await fetcher(url, accessToken);
      return [...defaultPresets, ...data];
    },
    { revalidateOnFocus: false }
  );

  useEffect(() => {
    let groupedByAlerts = {} as { [key: string]: AlertDto[] };

    // Fix the date format (it is received as text)
    alerts.forEach((alert) => {
      if (typeof alert.lastReceived === "string")
        alert.lastReceived = new Date(alert.lastReceived);
    });

    let aggregatedAlerts = alerts;

    if (groupBy) {
      // Group alerts by the groupBy key
      groupedByAlerts = alerts.reduce((acc, alert) => {
        const key = (alert as any)[groupBy] as string;
        if (!acc[key]) {
          acc[key] = [alert];
        } else {
          acc[key].push(alert);
        }
        return acc;
      }, groupedByAlerts);
      // Sort by last received
      Object.keys(groupedByAlerts).forEach((key) =>
        groupedByAlerts[key].sort(
          (a, b) => b.lastReceived.getTime() - a.lastReceived.getTime()
        )
      );
      // Only the last state of each alert is shown if we group by something
      aggregatedAlerts = Object.keys(groupedByAlerts).map(
        (key) => groupedByAlerts[key][0]
      );
    }

    setGroupedByAlerts(groupedByAlerts);
    setAggregatedAlerts(aggregatedAlerts);
  }, [alerts]);

  useEffect(() => {
    if (data) {
      setAlerts((prevAlerts) => Array.from(new Set([...data, ...prevAlerts])));
      if (pusherDisabled) setIsAsyncLoading(false);
    }
  }, [data, pusherDisabled]);

  useEffect(() => {
    if (!pusherDisabled && pusher) {
      console.log("Connecting to pusher");
      const channelName = `private-${tenantId}`;
      const channel = pusher.subscribe(channelName);

      channel.bind("async-alerts", function (base64CompressedAlert: string) {
        const decompressedAlert = zlib.inflateSync(
          Buffer.from(base64CompressedAlert, "base64")
        );
        const newAlerts = JSON.parse(
          new TextDecoder().decode(decompressedAlert)
        ) as AlertDto[];
        newAlerts.forEach((alert) => {
          if (typeof alert.lastReceived === "string")
            alert.lastReceived = new Date(alert.lastReceived);
        });
        setAlerts((prevAlerts) => {
          const combinedAlerts = [...prevAlerts, ...newAlerts];
          const uniqueObjectsMap = new Map();
          combinedAlerts.forEach((alert) => {
            uniqueObjectsMap.set(
              `${alert.id}-${alert.lastReceived.toISOString()}`,
              alert
            );
          });
          return Array.from(new Set(uniqueObjectsMap.values()));
        });
      });

      channel.bind("async-done", function () {
        setIsAsyncLoading(false);
      });
      console.log("Connected to pusher");
      return () => {
        pusher.unsubscribe(channelName);
      };
    } else {
      console.log("Pusher disabled");
    }
  }, [pusher, tenantId, pusherDisabled]);

  // Get a new searchParams string by merging the current
  // searchParams with a provided key/value pair
  // https://nextjs.org/docs/app/api-reference/functions/use-search-params

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
          alert.assignee = user.email;
        }
        return alert;
      })
    );
  };

  const setAssignee = (fingerprint: string, unassign: boolean) => {
    setAlerts((prevAlerts) =>
      prevAlerts.map((alert) => {
        if (alert.fingerprint === fingerprint) {
          alert.assignee = !unassign ? user?.email : "";
        }
        return alert;
      })
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
    return selectedOptions.some((option) => {
      const optionSplit = option.value.split("=");
      const key = optionSplit[0];
      const value = optionSplit[1]?.toLowerCase();
      if (typeof value === "string") {
        return ((alert as any)[key] as string)?.toLowerCase().includes(value);
      }
      return false;
    });
  }

  const currentStateAlerts = aggregatedAlerts
    .filter((alert) => showDeletedAlert(alert) && filterAlerts(alert))
    .sort((a, b) => b.lastReceived.getTime() - a.lastReceived.getTime())
    .slice(startIndex, endIndex);

  const TabContent = () => {
    return (
      <>
        <div className="flex w-full"></div>
        <AlertTable
          alerts={currentStateAlerts}
          groupedByAlerts={groupedByAlerts}
          groupBy="fingerprint"
          workflows={workflows}
          providers={providers?.installed_providers}
          mutate={() => mutate(null, { optimisticData: [] })}
          isAsyncLoading={isAsyncLoading}
          onDelete={onDelete}
          setAssignee={setAssignee}
          users={users}
          currentUser={user}
          openModal={openModal}
        />
      </>
    );
  };

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

  const deletedCount = !showDeleted
    ? aggregatedAlerts.filter((alert) =>
        alert.deleted.includes(alert.lastReceived.toISOString())
      ).length
    : 0;

  return (
    <>
      <Card className="mt-10 p-4 md:p-10 mx-auto">
        <TabGroup onIndexChange={onIndexChange} index={tabIndex}>
          <TabList className="mb-4" variant="line" color="orange">
            {presets!.map((preset, index) => (
              <Tab key={preset.name} tabIndex={index}>
                {preset.name}
              </Tab>
            ))}
          </TabList>
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
          />
          <TabPanels>
            {presets!.map((preset) => (
              <TabPanel key={preset.name}>
                <TabContent />
              </TabPanel>
            ))}
          </TabPanels>
        </TabGroup>
        <AlertPagination
          alerts={currentStateAlerts}
          mutate={mutate}
          setEndIndex={setEndIndex}
          setStartIndex={setStartIndex}
          deletedCount={deletedCount}
        />
      </Card>
      <AlertHistory
        isOpen={isOpen}
        closeModal={closeModal}
        data={selectedAlertHistory}
        users={users}
        currentUser={user}
      />
    </>
  );
}
