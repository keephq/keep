"use client";
import {
  Table,
  TableHead,
  TableHeaderCell,
  TableRow,
  MultiSelect,
  MultiSelectItem,
  Flex,
  Button,
  Callout,
  TabGroup,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
} from "@tremor/react";
import { Alert, AlertTableKeys } from "./models";
import {
  ArchiveBoxIcon,
  ExclamationCircleIcon,
  ServerIcon,
} from "@heroicons/react/20/solid";
import "./alerts.client.css";
import { useState } from "react";
import { getApiURL } from "../../utils/apiUrl";
import { useSession } from "../../utils/customAuth";
import useSWR from "swr";
import { fetcher } from "../../utils/fetcher";
import Loading from "../loading";
import { CircleStackIcon } from "@heroicons/react/24/outline";
import { AlertsTableBody } from "./alerts-table-body";

function onlyUnique(value: string, index: number, array: string[]) {
  return array.indexOf(value) === index;
}

export default function AlertsPage() {
  const apiUrl = getApiURL();
  const [selectedEnvironments, setSelectedEnvironments] = useState<string[]>(
    []
  );
  const { data: session, status, update } = useSession();
  const { data, error, isLoading } = useSWR<Alert[]>(
    `${apiUrl}/alerts`,
    (url) => fetcher(url, session?.accessToken!)
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
  if (status === "loading" || isLoading || !data) return <Loading />;
  if (status === "unauthenticated") return <div>Unauthenticated...</div>;

  const environments = data
    .map((alert) => alert.environment)
    .filter(onlyUnique);

  function environmentIsSeleected(alert: Alert): boolean {
    console.log(alert);
    console.log(selectedEnvironments);
    return (
      selectedEnvironments.includes(alert.environment) ||
      selectedEnvironments.length === 0
    );
  }

  return (
    <>
      <Flex justifyContent="between">
        <MultiSelect
          onValueChange={setSelectedEnvironments}
          placeholder="Select Environment..."
          className="max-w-xs mb-5"
          icon={ServerIcon}
        >
          {environments!.map((item) => (
            <MultiSelectItem key={item} value={item}>
              {item}
            </MultiSelectItem>
          ))}
        </MultiSelect>
        <Button
          icon={ArchiveBoxIcon}
          color="orange"
          size="xs"
          disabled={true}
          title="Coming Soon"
        >
          Export
        </Button>
      </Flex>
      {data.length === 0 ? (
        <Callout title="No Data" icon={CircleStackIcon} color="yellow">
          Please connect your providers to see alerts
        </Callout>
      ) : (
        <TabGroup>
          <TabList>
            <Tab>Pulled</Tab>
            <Tab>Pushed</Tab>
          </TabList>
          <TabPanels>
            <TabPanel>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>{/** For the menu */}</TableHeaderCell>
                    {AlertTableKeys.map((key) => (
                      <TableHeaderCell key={key}>{key}</TableHeaderCell>
                    ))}
                  </TableRow>
                </TableHead>
                <AlertsTableBody
                  data={data.filter(
                    (alert) => !alert.pushed && environmentIsSeleected(alert)
                  )}
                />
              </Table>
            </TabPanel>
            <TabPanel>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>{/** For the menu */}</TableHeaderCell>
                    {AlertTableKeys.map((key) => (
                      <TableHeaderCell key={key}>{key}</TableHeaderCell>
                    ))}
                  </TableRow>
                </TableHead>
                <AlertsTableBody
                  data={data.filter(
                    (alert) => alert.pushed && environmentIsSeleected(alert)
                  )}
                />
              </Table>
            </TabPanel>
          </TabPanels>
        </TabGroup>
      )}
    </>
  );
}
