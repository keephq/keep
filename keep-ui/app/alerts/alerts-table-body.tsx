import { ShieldCheckIcon } from "@heroicons/react/24/outline";
import {
  TableBody,
  TableRow,
  TableCell,
  CategoryBar,
  Icon,
  Accordion,
  AccordionHeader,
  AccordionBody,
  BadgeDelta,
  DeltaType,
  Button,
} from "@tremor/react";
import { Alert, AlertKnownKeys, Severity } from "./models";
import Image from "next/image";

interface Props {
  data: Alert[];
  groupBy?: string;
  groupedByData?: { [key: string]: Alert[] };
  openModal?: (alert: Alert) => void;
}

const getSeverity = (severity: Severity | undefined) => {
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
      color=""
    />
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
            <TableCell className="text-center">
              {getSeverity(alert.severity)}
            </TableCell>
            <TableCell className="max-w-[340px] truncate" title={alert.name}>
              {alert.name}
            </TableCell>
            <TableCell>{alert.description}</TableCell>
            <TableCell>{alert.status}</TableCell>
            <TableCell>{getAlertLastReceieved(alert)}</TableCell>
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

            <TableCell>
              <CategoryBar
                values={[40, 30, 20, 10]}
                colors={["emerald", "yellow", "orange", "rose"]}
                markerValue={alert.fatigueMeter ?? 0}
                tooltip={alert.fatigueMeter?.toString() ?? "0"}
                className="w-48"
              />
            </TableCell>
            <TableCell>List of workflows refs</TableCell>
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
          </TableRow>
        );
      })}
    </TableBody>
  );
}
