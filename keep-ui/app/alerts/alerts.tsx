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
import "./alerts.client.css";

export default function Alerts({
  accessToken,
  tenantId,
}: {
  accessToken: string;
  tenantId: string;
}) {
  const apiUrl = getApiURL();
  const [selectedEnvironments, setSelectedEnvironments] = useState<string[]>(
    []
  );
  const [isSlowLoading, setIsSlowLoading] = useState<boolean>(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertNameSearchString, setAlertNameSearchString] =
    useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string[]>([]);
  const [reloadLoading, setReloadLoading] = useState<boolean>(false);
  const [isAsyncLoading, setIsAsyncLoading] = useState<boolean>(true);
  const { data, error, isLoading, mutate } = useSWR<Alert[]>(
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

  useEffect(() => {
    if (data)
      setAlerts((prevAlerts) => Array.from(new Set([...data, ...prevAlerts])));
  }, [data]);

  useEffect(() => {
    if (tenantId) {
      const pusher = new Pusher(process.env.NEXT_PUBLIC_PUSHER_APP_KEY!, {
        wsHost: process.env.NEXT_PUBLIC_PUSHER_HOST,
        wsPort: process.env.NEXT_PUBLIC_PUSHER_PORT
          ? parseInt(process.env.NEXT_PUBLIC_PUSHER_PORT)
          : undefined,
        forceTLS: false,
        disableStats: true,
        enabledTransports: ["ws", "wss"],
        cluster: process.env.NEXT_PUBLIC_PUSHER_CLUSTER || "local",
        channelAuthorization: {
          transport: "ajax",
          endpoint: `${getApiURL()}/pusher/auth`,
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        },
      });

      const channelName = `private-${tenantId}`;
      const channel = pusher.subscribe(channelName);

      channel.bind("async-alerts", function (newAlerts: Alert[]) {
        setAlerts((prevAlerts) =>
          Array.from(new Set([...prevAlerts, ...newAlerts]))
        );
      });

      channel.bind("async-done", function (data: any) {
        setIsAsyncLoading(false);
      });

      return () => {
        pusher.unsubscribe(channelName);
      };
    }
  }, [tenantId, accessToken]);

  if (isLoading) return <Loading slowLoading={isSlowLoading} />;

  const environments = alerts
    .map((alert) => alert.environment.toLowerCase())
    .filter(onlyUnique);

  function environmentIsSeleected(alert: Alert): boolean {
    return (
      selectedEnvironments.includes(alert.environment.toLowerCase()) ||
      selectedEnvironments.length === 0
    );
  }

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

  const statuses = alerts.map((alert) => alert.status).filter(onlyUnique);

  function statusIsSeleected(alert: Alert): boolean {
    return selectedStatus.includes(alert.status) || selectedStatus.length === 0;
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
        data={alerts
          .map((alert) => {
            alert.lastReceived = new Date(alert.lastReceived);
            return alert;
          })
          .filter(
            (alert) =>
              environmentIsSeleected(alert) &&
              statusIsSeleected(alert) &&
              searchAlert(alert)
          )}
        groupBy="fingerprint"
        workflows={workflows}
        providers={providers?.installed_providers}
        mutate={() => mutate(null, { optimisticData: [] })}
        isAsyncLoading={isAsyncLoading}
      />
    </Card>
  );
}
