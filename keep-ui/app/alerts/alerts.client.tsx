"use client";
import {
  Table,
  TableHead,
  TableHeaderCell,
  TableBody,
  TableRow,
  TableCell,
  BadgeDelta,
  DeltaType,
  Icon,
  MultiSelect,
  MultiSelectItem,
  CategoryBar,
  Flex,
  Button,
  Callout,
} from "@tremor/react";
import Image from "next/image";
import { Alert, AlertTableKeys, Severity } from "./models";
import {
  ArchiveBoxIcon,
  ExclamationCircleIcon,
  ServerIcon,
  ShieldCheckIcon,
} from "@heroicons/react/20/solid";
import "./alerts.client.css";
import { useState } from "react";
import { getApiURL } from "../../utils/apiUrl";
import { mockAlerts } from "./mock-data";
import { useSession } from "../../utils/customAuth";
import useSWR from "swr";
import { fetcher } from "../../utils/fetcher";
import Loading from "../loading";
import { CircleStackIcon } from "@heroicons/react/24/outline";

function getSeverity(severity: Severity | undefined) {
  let deltaType: string;
  switch (severity) {
    case "critical":
      deltaType = "increase";
      break;
    case "high":
      deltaType = "moderateIncrease";
      break;
    case "medium":
      deltaType = "unchanged";
      break;
    case "low":
      deltaType = "moderateDecrease";
      break;
    default:
      deltaType = "decrease";
      break;
  }
  return (
    <BadgeDelta
      title={severity?.toString() ?? "lowest"}
      deltaType={deltaType as DeltaType}
    />
  );
}

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
  const environmentIsSeleected = (alert: Alert) =>
    selectedEnvironments.length === 0 ||
    selectedEnvironments.includes(alert.environment);

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
        <Callout title="No Data" icon={CircleStackIcon} color="yellow" />
      ) : (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>{/** For the menu */}</TableHeaderCell>
              {AlertTableKeys.map((key) => (
                <TableHeaderCell key={key}>{key}</TableHeaderCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {data
              .filter((alert) => environmentIsSeleected(alert))
              .map((alert) => {
                return (
                  <TableRow key={alert.id}>
                    <TableCell>
                      <div className="menu"></div>
                    </TableCell>
                    <TableCell className="text-center">
                      {getSeverity(alert.severity)}
                    </TableCell>
                    <TableCell>{alert.status}</TableCell>
                    <TableCell>
                      <CategoryBar
                        values={[40, 30, 20, 10]}
                        colors={["emerald", "yellow", "orange", "rose"]}
                        markerValue={alert.fatigueMeter ?? 0}
                        tooltip={alert.fatigueMeter?.toString() ?? "0"}
                        className="w-48"
                      />
                    </TableCell>
                    <TableCell>{alert.lastReceived.toString()}</TableCell>
                    <TableCell className="text-center" align="center">
                      {alert.isDuplicate ? (
                        <Icon
                          icon={ShieldCheckIcon}
                          variant="light"
                          color="orange"
                          tooltip={
                            alert.duplicateReason ?? "This alert is a duplicate"
                          }
                          size="xs"
                        />
                      ) : null}
                    </TableCell>
                    <TableCell>{alert.environment}</TableCell>
                    <TableCell>{alert.service}</TableCell>
                    <TableCell>
                      {alert.source?.map((source, index) => {
                        return (
                          <Image
                            className={`inline-block rounded-full ${
                              index == 0 ? "" : "-ml-2"
                            }`}
                            key={source}
                            alt={source}
                            height={24}
                            width={24}
                            title={source}
                            src={`/icons/${source}-icon.png`}
                          />
                        );
                      })}
                    </TableCell>
                    <TableCell>{alert.message}</TableCell>
                    <TableCell>{alert.description}</TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
      )}
    </>
  );
}
