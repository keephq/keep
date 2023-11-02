import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  Icon,
  Callout,
} from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { Alert, AlertTableKeys } from "./models";
import { useState } from "react";
import { AlertTransition } from "./alert-transition";
import {
  CircleStackIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { Provider } from "app/providers/providers";

interface Props {
  data: Alert[];
  groupBy?: string;
  workflows?: any[];
  providers?: Provider[];
  mutate: () => void;
}

export function AlertTable({ data, groupBy, workflows, providers, mutate }: Props) {
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
    // Sort by last received
    Object.keys(groupedByData).forEach((key) =>
      groupedByData[key].sort(
        (a, b) => b.lastReceived.getTime() - a.lastReceived.getTime()
      )
    );
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

  return data.length === 0 ? (
    <Callout
      title="No Data"
      icon={CircleStackIcon}
      color="yellow"
      className="mt-5"
    >
      Please connect supported providers to see alerts
    </Callout>
  ) : (
    <>
      <Table>
        <TableHead>
          <TableRow>
            {<TableHeaderCell>{/** Menu */}</TableHeaderCell>}
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
          workflows={workflows}
          providers={providers}
          mutate={mutate}
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
