import {
  ArrowPathIcon,
  BellAlertIcon,
  MagnifyingGlassIcon,
  ServerStackIcon,
} from "@heroicons/react/24/outline";
import {
  MultiSelect,
  MultiSelectItem,
  Flex,
  TextInput,
  Button,
  Card,
  Switch,
} from "@tremor/react";
import useSWR from "swr";
import { fetcher } from "utils/fetcher";
import { onlyUnique } from "utils/helpers";
import { AlertTable } from "./alert-table";
import { Alert } from "./models";
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

export default function Alerts({
  accessToken,
  tenantId,
  pusher,
  user,
}: {
  accessToken: string;
  tenantId: string;
  pusher: Pusher;
  user: NextUser;
}) {
  const apiUrl = getApiURL();
  const [selectedEnvironments, setSelectedEnvironments] = useState<string[]>(
    []
  );
  const [showDeleted, setShowDeleted] = useState<boolean>(false);
  const [onlyDeleted, setOnlyDeleted] = useState<boolean>(false);
  const [isSlowLoading, setIsSlowLoading] = useState<boolean>(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [aggregatedAlerts, setAggregatedAlerts] = useState<Alert[]>([]);
  const [groupedByAlerts, setGroupedByAlerts] = useState<{
    [key: string]: Alert[];
  }>({});
  const [alertNameSearchString, setAlertNameSearchString] =
    useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string[]>([]);
  const [reloadLoading, setReloadLoading] = useState<boolean>(false);
  const [isAsyncLoading, setIsAsyncLoading] = useState<boolean>(true);
  const { data, isLoading, mutate } = useSWR<Alert[]>(
    `${apiUrl}/alerts`,
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

  useEffect(() => {
    const groupBy = "fingerprint"; // TODO: in the future, we'll allow to modify this
    let groupedByAlerts = {} as { [key: string]: Alert[] };

    // Fix the date format (it is received as text)
    let aggregatedAlerts = alerts.map((alert) => {
      alert.lastReceived = new Date(alert.lastReceived);
      return alert;
    });

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
    if (data)
      setAlerts((prevAlerts) => Array.from(new Set([...data, ...prevAlerts])));
  }, [data]);

  useEffect(() => {
    console.log("Connecting to pusher");
    const channelName = `private-${tenantId}`;
    const channel = pusher.subscribe(channelName);

    channel.bind("async-alerts", function (base64CompressedAlert: string) {
      const decompressedAlert = zlib.inflateSync(
        Buffer.from(base64CompressedAlert, "base64")
      );
      const newAlerts = JSON.parse(
        new TextDecoder().decode(decompressedAlert)
      ) as Alert[];
      setAlerts((prevAlerts) =>
        Array.from(new Set([...newAlerts, ...prevAlerts]))
      );
    });

    channel.bind("async-done", function () {
      setIsAsyncLoading(false);
    });
    console.log("Connected to pusher");
    return () => {
      pusher.unsubscribe(channelName);
    };
  }, [pusher, tenantId]);

  if (isLoading) return <Loading slowLoading={isSlowLoading} />;

  const environments = aggregatedAlerts
    .map((alert) => alert.environment.toLowerCase())
    .filter(onlyUnique);

  function environmentIsSeleected(alert: Alert): boolean {
    return (
      selectedEnvironments.includes(alert.environment.toLowerCase()) ||
      selectedEnvironments.length === 0
    );
  }

  const onDelete = (fingerprint: string, restore: boolean = false) => {
    setAlerts((prevAlerts) =>
      prevAlerts.map((alert) => {
        if (alert.fingerprint === fingerprint) {
          alert.deleted = !restore;
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

  function searchAlert(alert: Alert): boolean {
    return (
      alertNameSearchString === "" ||
      alertNameSearchString === undefined ||
      alertNameSearchString === null ||
      alert.name.toLowerCase().includes(alertNameSearchString.toLowerCase()) ||
      alert.description
        ?.toLowerCase()
        .includes(alertNameSearchString.toLowerCase()) ||
      false
    );
  }

  const statuses = aggregatedAlerts
    .map((alert) => alert.status)
    .filter(onlyUnique);

  function statusIsSeleected(alert: Alert): boolean {
    return selectedStatus.includes(alert.status) || selectedStatus.length === 0;
  }

  function showDeletedAlert(alert: Alert): boolean {
    if (showDeleted && onlyDeleted) return alert.deleted === true;
    return showDeleted || !alert.deleted;
  }

  return (
    <Card className="mt-10 p-4 md:p-10 mx-auto">
      <Flex justifyContent="between" alignItems="center">
        <div className="flex w-full">
          <MultiSelect
            onValueChange={setSelectedEnvironments}
            placeholder="Select Environment..."
            className="max-w-xs"
            icon={ServerStackIcon}
          >
            {environments!.map((item) => (
              <MultiSelectItem key={item} value={item}>
                {item}
              </MultiSelectItem>
            ))}
          </MultiSelect>
          <MultiSelect
            onValueChange={setSelectedStatus}
            placeholder="Select Status..."
            className="max-w-xs ml-2.5"
            icon={BellAlertIcon}
          >
            {statuses!.map((item) => (
              <MultiSelectItem key={item} value={item}>
                {item}
              </MultiSelectItem>
            ))}
          </MultiSelect>
          <TextInput
            className="max-w-xs ml-2.5"
            icon={MagnifyingGlassIcon}
            placeholder="Search Alert..."
            value={alertNameSearchString}
            onChange={(e) => setAlertNameSearchString(e.target.value)}
          />
          <div className="flex items-center space-x-3 ml-2.5">
            <Switch
              id="switch"
              name="switch"
              checked={showDeleted}
              onChange={setShowDeleted}
              color={"orange"}
            />
            <label htmlFor="switch" className="text-sm text-gray-500">
              Show Deleted
            </label>
          </div>
          <div
            className={`flex items-center space-x-3 ml-2.5 ${
              showDeleted ? "" : "hidden"
            }`}
          >
            <Switch
              id="switch"
              name="switch"
              checked={onlyDeleted}
              onChange={setOnlyDeleted}
              color={"orange"}
            />
            <label htmlFor="switch" className="text-sm text-gray-500">
              Only Deleted
            </label>
          </div>
        </div>
        <Button
          icon={ArrowPathIcon}
          color="orange"
          size="xs"
          disabled={reloadLoading}
          loading={reloadLoading}
          onClick={async () => {
            setReloadLoading(true);
            await mutate();
            setReloadLoading(false);
          }}
          title="Refresh"
        ></Button>
      </Flex>
      <AlertTable
        alerts={aggregatedAlerts.filter(
          (alert) =>
            environmentIsSeleected(alert) &&
            statusIsSeleected(alert) &&
            searchAlert(alert) &&
            showDeletedAlert(alert)
        )}
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
        deletedCount={!showDeleted ? aggregatedAlerts.filter((alert) => alert.deleted).length : 0}
      />
    </Card>
  );
}
