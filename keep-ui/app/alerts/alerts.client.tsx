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
  MultiSelectBox,
  MultiSelectBoxItem,
  CategoryBar,
  Flex,
  Button,
} from "@tremor/react";
import Image from "next/image";
import { Alert, AlertTableKeys, Severity } from "./models";
import {
  ArchiveBoxIcon,
  ServerIcon,
  ShieldCheckIcon,
} from "@heroicons/react/20/solid";
import "./alerts.client.css";
import { useState } from "react";

const mockAlerts: Alert[] = [
  {
    id: "1",
    name: "CPU usage",
    severity: "critical" as Severity,
    status: "active",
    lastReceived: new Date(),
    environment: "production",
    isDuplicate: true,
    service: "backend",
    source: ["datadog"],
    message: "CPU usage is above 90%",
    description:
      "The CPU usage on server-1 is above 90% and requires attention",
    fatigueMeter: Math.floor(Math.random() * 100),
  },
  {
    id: "2",
    name: "Memory usage",
    severity: "high" as Severity,
    status: "active",
    lastReceived: new Date(),
    environment: "staging",
    isDuplicate: false,
    service: "frontend",
    source: ["elastic", "datadog"],
    message: "Memory usage is above 80%",
    description:
      "The memory usage on client-1 is above 80% and requires attention",
    fatigueMeter: Math.floor(Math.random() * 100),
  },
  {
    id: "3",
    name: "Disk space",
    severity: "medium" as Severity,
    status: "resolved",
    lastReceived: new Date(),
    environment: "development",
    isDuplicate: true,
    service: "database",
    source: ["grafana", "snowflake"],
    message: "Disk space is running low",
    description: "The disk space on db-1 is running low and requires attention",
    fatigueMeter: Math.floor(Math.random() * 100),
  },
  {
    id: "4",
    name: "Network latency",
    severity: "medium" as Severity,
    status: "active",
    lastReceived: new Date(),
    environment: "production",
    isDuplicate: false,
    service: "backend",
    source: ["datadog"],
    message: "Network latency is above threshold",
    description:
      "The network latency on server-2 is above the threshold and requires attention",
    fatigueMeter: Math.floor(Math.random() * 100),
  },
  {
    id: "5",
    name: "Disk I/O",
    severity: "low" as Severity,
    status: "active",
    lastReceived: new Date(),
    environment: "staging",
    isDuplicate: true,
    duplicateReason: "Alert triggered multiple times",
    service: "frontend",
    source: ["pagerduty"],
    message: "Disk I/O is above average",
    description:
      "The disk I/O on client-2 is above average and requires attention",
    fatigueMeter: Math.floor(Math.random() * 100),
  },
  {
    id: "6",
    name: "Database connection",
    severity: "low" as Severity,
    status: "resolved",
    lastReceived: new Date(),
    environment: "development",
    isDuplicate: false,
    service: "database",
    source: ["sentry", "snowflake"],
    message: "Lost connection to the database",
    description: "The connection to db-2 was lost and has been restored",
    fatigueMeter: Math.floor(Math.random() * 100),
  },
  {
    id: "7",
    name: "Server response time",
    severity: "low" as Severity,
    status: "active",
    lastReceived: new Date(),
    environment: "production",
    isDuplicate: true,
    duplicateReason: "Triggered in both Datadog and Snowflake",
    service: "backend",
    source: ["snowflake", "datadog"],
    message: "Server response time is too slow",
    description:
      "The response time on server-3 is too slow and requires attention",
    fatigueMeter: Math.floor(Math.random() * 100),
  },
  {
    id: "8",
    name: "Cache utilization",
    status: "active",
    lastReceived: new Date(),
    environment: "staging",
    isDuplicate: false,
    service: "frontend",
    source: ["elastic", "datadog", "sentry"],
    message: "Cache utilization is below threshold",
    description:
      "The cache utilization on client-3 is below the threshold and requires attention",
    fatigueMeter: Math.floor(Math.random() * 100),
  },
];

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
  const [selectedEnvironments, setSelectedEnvironments] = useState<string[]>(
    []
  );

  const environments = mockAlerts
    .map((alert) => alert.environment)
    .filter(onlyUnique);
  const environmentIsSeleected = (alert: Alert) =>
    selectedEnvironments.length === 0 ||
    selectedEnvironments.includes(alert.environment);

  return (
    <>
      <Flex justifyContent="between">
        <MultiSelectBox
          onValueChange={setSelectedEnvironments}
          placeholder="Select Environment..."
          className="max-w-xs mb-5"
          icon={ServerIcon}
        >
          {environments.map((item) => (
            <MultiSelectBoxItem key={item} value={item}>
              {item}
            </MultiSelectBoxItem>
          ))}
        </MultiSelectBox>
        <Button icon={ArchiveBoxIcon} color="orange" size="xs" disabled={true}>
          Export 🚧
        </Button>
      </Flex>
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
          {mockAlerts
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
                      categoryPercentageValues={[40, 30, 20, 10]}
                      colors={["emerald", "yellow", "orange", "rose"]}
                      percentageValue={alert.fatigueMeter}
                      tooltip={alert.fatigueMeter?.toString()}
                      className="w-48"
                    />
                  </TableCell>
                  <TableCell>{alert.lastReceived.toDateString()}</TableCell>
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
    </>
  );
}
