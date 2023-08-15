import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  Icon,
} from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { Alert, AlertTableKeys } from "./models";
import { useState } from "react";
import { AlertTransition } from "./alert-transition";
import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";

interface Props {
  data: Alert[];
  groupBy?: string;
}

export function AlertTable({ data, groupBy }: Props) {
  const [selectedAlertHistory, setSelectedAlertHistory] = useState<Alert[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  let groupedByData = {} as { [key: string]: Alert[] };
  let aggregatedData = data;
  if (groupBy) {
    // Group alerts by the groupBy key
    groupedByData = data.reduce((acc, alert) => {
      const key = (alert as any)[groupBy] as string;
      if (!acc[key]) {
        acc[key] = [alert];
      } else {
        acc[key].push(alert);
      }
      return acc;
    }, groupedByData);
    // Only the last state of each alert is shown if we group by something
    aggregatedData = Object.keys(groupedByData).map(
      (key) => groupedByData[key][0]
    );
  }

  const closeModal = (): any => setIsOpen(false);
  const openModal = (alert: Alert): any => {
    setSelectedAlertHistory(groupedByData[(alert as any)[groupBy!]]);
    setIsOpen(true);
  };

  return (
    <>
      <Table>
        <TableHead>
          <TableRow>
            {groupBy && <TableHeaderCell>History</TableHeaderCell>}
            {Object.keys(AlertTableKeys).map((key) => (
              <TableHeaderCell key={key}>
                <div className="flex items-center">
                  {key}{" "}
                  {AlertTableKeys[key] !== "" && (
                    <Icon
                      icon={QuestionMarkCircleIcon}
                      tooltip={AlertTableKeys[key]}
                      variant="simple"
                      color="gray"
                    />
                  )}{" "}
                </div>
              </TableHeaderCell>
            ))}
          </TableRow>
        </TableHead>
        <AlertsTableBody
          data={aggregatedData}
          groupBy={groupBy}
          groupedByData={groupedByData}
          openModal={openModal}
        />
      </Table>
      <AlertTransition
        isOpen={isOpen}
        closeModal={closeModal}
        data={selectedAlertHistory}
      />
    </>
  );
}
