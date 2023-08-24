import {
  ArrowDownIcon,
  ArrowDownRightIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  ArrowUpRightIcon,
  ShieldCheckIcon,
} from "@heroicons/react/24/outline";
import {
  TableBody,
  TableRow,
  TableCell,
  CategoryBar,
  Icon,
  Accordion,
  AccordionHeader,
  AccordionBody,
  Button,
  Badge,
} from "@tremor/react";
import { Alert, AlertKnownKeys, Severity } from "./models";
import Image from "next/image";
import "./alerts-table-body.css";

interface Props {
  data: Alert[];
  groupBy?: string;
  groupedByData?: { [key: string]: Alert[] };
  openModal?: (alert: Alert) => void;
}

const getSeverity = (severity: Severity | undefined) => {
  let icon: any;
  let color: any;
  let severityText: string;
  switch (severity) {
    case "critical":
      icon = ArrowUpIcon;
      color = "red";
      severityText = Severity.Critical.toString();
      break;
    case "high":
      icon = ArrowUpRightIcon;
      color = "orange";
      severityText = Severity.High.toString();
      break;
    case "medium":
      color = "yellow";
      icon = ArrowRightIcon;
      severityText = Severity.Medium.toString();
      break;
    case "low":
      icon = ArrowDownRightIcon;
      color = "green";
      severityText = Severity.Low.toString();
      break;
    default:
      icon = ArrowDownIcon;
      color = "emerald";
      severityText = Severity.Info.toString();
      break;
  }
  return (
    <Badge
      //deltaType={deltaType as DeltaType}
      color={color}
      icon={icon}
      tooltip={severityText}
      size="xs"
    ></Badge>
  );
};

export function AlertsTableBody({
  data,
  groupBy,
  groupedByData,
  openModal,
}: Props) {
  const getAlertLastReceieved = (alert: Alert) => {
    let lastReceived = "unknown";
    if (alert.lastReceived) {
      try {
        lastReceived = new Date(alert.lastReceived).toISOString();
      } catch {}
    }
    return lastReceived;
  };

  return (
    <TableBody>
      {data.map((alert) => {
        const extraPayload = Object.keys(alert)
          .filter((key) => !AlertKnownKeys.includes(key))
          .reduce((obj, key) => {
            return {
              ...obj,
              [key]: (alert as any)[key],
            };
          }, {});
        const extraIsEmpty = Object.keys(extraPayload).length === 0;
        return (
          <TableRow key={alert.id}>
            {/* <TableCell>
              <div className="menu"></div>
            </TableCell> */}
            {groupBy && groupedByData && openModal ? (
              <TableCell>
                <Button
                  size="xs"
                  variant="secondary"
                  color="gray"
                  disabled={!groupedByData[(alert as any)[groupBy]]}
                  onClick={() => openModal(alert)}
                >
                  Open
                </Button>
              </TableCell>
            ) : null}
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
            <TableCell>{getAlertLastReceieved(alert)}</TableCell>
            <TableCell className="text-center" align="center">
              {alert.isDuplicate ? (
                <Icon
                  icon={ShieldCheckIcon}
                  variant="light"
                  color="orange"
                  tooltip={alert.duplicateReason ?? "This alert is a duplicate"}
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
            <TableCell className="max-w-[340px] truncate" title={alert.name}>
              {alert.name}
            </TableCell>
            <TableCell>{alert.description}</TableCell>
            <TableCell className="max-w-[340px] truncate" title={alert.message}>
              {alert.message}
            </TableCell>
            <TableCell className="w-96">
              {extraIsEmpty ? null : (
                <Accordion>
                  <AccordionHeader className="w-96">
                    Extra Payload
                  </AccordionHeader>
                  <AccordionBody>
                    <pre className="w-80 overflow-y-scroll">
                      {JSON.stringify(extraPayload, null, 2)}
                    </pre>
                  </AccordionBody>
                </Accordion>
              )}
            </TableCell>
          </TableRow>
        );
      })}
    </TableBody>
  );
}
