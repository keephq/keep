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
} from "@tremor/react";
import { Alert, AlertKnownKeys, Severity } from "./models";
import Image from "next/image";

interface Props {
  data: Alert[];
}

export function AlertsTableBody({ data }: Props) {
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
            <TableCell>{new Date(alert.lastReceived).toISOString()}</TableCell>
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
            <TableCell>{alert.description}</TableCell>
            <TableCell>{alert.message}</TableCell>
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
