import {
  BellAlertIcon,
  MagnifyingGlassIcon,
  ServerStackIcon,
} from "@heroicons/react/24/outline";
import { ExclamationCircleIcon } from "@heroicons/react/20/solid";
import {
  MultiSelect,
  MultiSelectItem,
  Flex,
  Callout,
  TextInput,
} from "@tremor/react";
import useSWR from "swr";
import { fetcher } from "utils/fetcher";
import { onlyUnique } from "utils/helpers";
import { AlertTable } from "./alert-table";
import { Alert } from "./models";
import { getApiURL } from "utils/apiUrl";
import { useState } from "react";
import Loading from "app/loading";
import { Workflow } from "app/workflows/models";
import "./alerts.client.css";
import { ProvidersResponse } from "app/providers/providers";

export default function Alerts({ accessToken }: { accessToken: string }) {
  const apiUrl = getApiURL();
  const [selectedEnvironments, setSelectedEnvironments] = useState<string[]>(
    []
  );
  const [alertNameSearchString, setAlertNameSearchString] =
    useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string[]>([]);
  const { data, error, isLoading, mutate } = useSWR<Alert[]>(
    `${apiUrl}/alerts`,
    (url) => fetcher(url, accessToken)
  );
  const { data: workflows } = useSWR<Workflow[]>(`${apiUrl}/workflows`, (url) =>
    fetcher(url, accessToken)
  );
  const { data: providers } = useSWR<ProvidersResponse>(
    `${apiUrl}/providers`,
    (url) => fetcher(url, accessToken)
  );

  if (error) {
    return (
      <Callout
        className="mt-4"
        title="Error"
        icon={ExclamationCircleIcon}
        color="rose"
      >
        Failed to load alerts
      </Callout>
    );
  }
  if (isLoading || !data) return <Loading />;

  const environments = data
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

  const statuses = data.map((alert) => alert.status).filter(onlyUnique);

  function statusIsSeleected(alert: Alert): boolean {
    return selectedStatus.includes(alert.status) || selectedStatus.length === 0;
  }

  return (
    <>
      <Flex justifyContent="between">
        <div className="flex w-full">
          <MultiSelect
            onValueChange={setSelectedEnvironments}
            placeholder="Select Environment..."
            className="max-w-xs mb-5"
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
            className="max-w-xs mb-5 ml-2.5"
            icon={BellAlertIcon}
          >
            {statuses!.map((item) => (
              <MultiSelectItem key={item} value={item}>
                {item}
              </MultiSelectItem>
            ))}
          </MultiSelect>
          <TextInput
            className="max-w-xs mb-5 ml-2.5"
            icon={MagnifyingGlassIcon}
            placeholder="Search Alert..."
            value={alertNameSearchString}
            onChange={(e) => setAlertNameSearchString(e.target.value)}
          />
        </div>
        {/* <Button
          icon={ArchiveBoxIcon}
          color="orange"
          size="xs"
          disabled={true}
          title="Coming Soon"
        >
          Export
        </Button> */}
      </Flex>
      <AlertTable
        data={data
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
        groupBy="name"
        workflows={workflows}
        providers={providers?.installed_providers}
        mutate={mutate}
      />
    </>
  );
}
